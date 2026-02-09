"""
Утилита для обновления БД из конкурсных списков
ФИНАЛЬНАЯ ВЕРСИЯ - RAW SQL для удаления, предотвращение взрыва памяти
"""
import logging
import time
from datetime import date
from typing import Dict, List, Set, Tuple
from collections import defaultdict

from django.db import transaction, connection

from applicants.models import Applicant
from admissions.models import Program, Application

logger = logging.getLogger(__name__)


class DBUpdater:
    """Класс для оптимизированного обновления БД"""
    
    BATCH_SIZE = 1000
    
    @staticmethod
    def _get_programs_cache() -> Dict[str, Program]:
        """Получает кэш программ"""
        return {prog.code: prog for prog in Program.objects.all()}
    
    @staticmethod
    def _collect_data(parsed_files: List[Dict], programs_cache: Dict[str, Program]):
        """
        Собирает данные из всех файлов в структуры для bulk операций
        
        ВАЛИДАЦИЯ: проверяет, что нет дубликатов (applicant_id, program, date)
        
        Returns:
            Tuple of:
            - all_applicant_data: Dict[int, Dict] - данные абитуриентов
            - applications_by_date: Dict[date, List[Dict]] - заявления по датам
            - dates_set: Set[date] - уникальные даты
            - applicant_ids_set: Set[int] - уникальные ID абитуриентов
        """
        all_applicant_data = {}
        applications_by_date = defaultdict(list)
        all_applicant_ids = set()
        all_dates = set()
        
        # Для отслеживания дубликатов
        seen_applications = defaultdict(set)  # date -> set of (applicant_id, program_code)
        
        # Собираем данные из всех файлов
        for parsed_file in parsed_files:
            date = parsed_file['date']
            all_dates.add(date)
            
            program = programs_cache.get(parsed_file['program_code'])
            
            if not program:
                logger.error(f"Программа {parsed_file['program_code']} не найдена в кэше")
                continue
            
            for record in parsed_file['records']:
                applicant_id = record['applicant_id']
                all_applicant_ids.add(applicant_id)
                
                # Данные абитуриента (последнее значение перезапишет предыдущие)
                all_applicant_data[applicant_id] = {
                    'physics_ict_score': record['physics_ict_score'],
                    'russian_score': record['russian_score'],
                    'math_score': record['math_score'],
                    'achievements_score': record['achievements_score'],
                    'total_score': record['total_score'],
                }
                
                # ============================================

                key = (applicant_id, program.code)
                
                if key in seen_applications[date]:
                    raise ValueError(
                        f"ОШИБКА В ДАННЫХ: Абитуриент {applicant_id} имеет несколько "
                        f"заявлений на программу {program.code} для даты {date}. "
                        f"Это логически невозможно - один абитуриент может подать "
                        f"только ОДНО заявление на каждую программу с одним приоритетом. "
                        f"Проверьте корректность генерации CSV файлов."
                    )
                
                seen_applications[date].add(key)
                
                # Заявление на программу
                applications_by_date[date].append({
                    'applicant_id': applicant_id,
                    'program': program,
                    'priority': record['priority'],
                    'consent': record['consent'],
                })
        
        logger.info(
            f"Собрано: {len(all_applicant_ids)} уникальных абитуриентов, "
            f"{len(all_dates)} дат, "
            f"{sum(len(apps) for apps in applications_by_date.values())} заявлений"
        )
        
        return (
            all_applicant_data,
            dict(applications_by_date),
            all_dates,
            all_applicant_ids
        )
    
    @staticmethod
    def _upsert_applicants(
        all_applicant_data: Dict[int, Dict],
        applicant_ids_set: Set[int],
        stats: Dict
    ):
        """
        Создание/обновление абитуриентов
        """
        # Получаем существующих абитуриентов
        existing_applicants = set(
            Applicant.objects.filter(
                applicant_id__in=applicant_ids_set
            ).values_list('applicant_id', flat=True)
        )
        
        logger.info(f"Найдено существующих абитуриентов: {len(existing_applicants)}")
        
        # ============================================

        applicants_to_create = []
        
        for applicant_id, data in all_applicant_data.items():
            if applicant_id not in existing_applicants:
                applicants_to_create.append(Applicant(
                    applicant_id=applicant_id,
                    physics_ict_score=data['physics_ict_score'],
                    russian_score=data['russian_score'],
                    math_score=data['math_score'],
                    achievements_score=data['achievements_score'],
                    total_score=data['total_score']
                ))
        
        if applicants_to_create:
            Applicant.objects.bulk_create(
                applicants_to_create,
                batch_size=DBUpdater.BATCH_SIZE,
                ignore_conflicts=True
            )
            stats['applicants_created'] += len(applicants_to_create)
            logger.info(f"[+] Создано абитуриентов: {len(applicants_to_create)}")
        
        # ============================================

        if existing_applicants:
            update_data = []
            for applicant_id in existing_applicants:
                if applicant_id in all_applicant_data:
                    data = all_applicant_data[applicant_id]
                    update_data.append((
                        data['physics_ict_score'],
                        data['russian_score'],
                        data['math_score'],
                        data['achievements_score'],
                        data['total_score'],
                        applicant_id
                    ))
            
            if update_data:
                with connection.cursor() as cursor:
                    cursor.executemany(
                        """
                        UPDATE applicants 
                        SET physics_ict_score = %s,
                            russian_score = %s,
                            math_score = %s,
                            achievements_score = %s,
                            total_score = %s,
                            updated_at = NOW()
                        WHERE applicant_id = %s
                        """,
                        update_data
                    )
                
                stats['applicants_updated'] += len(update_data)
                logger.info(f"[~] Обновлено абитуриентов: {len(update_data)}")
    
    @staticmethod
    def _update_applications_for_date(
        app_date: date,
        new_applications: List[Dict],
        applicant_ids: Set[int],
        programs_cache: Dict[str, Program],
        stats: Dict
    ):
        """
        Обновление заявлений для конкретной даты
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: RAW SQL DELETE без загрузки объектов в память
        """
        logger.info(f"[ДАТА] Обработка даты {app_date}: {len(new_applications)} заявлений")
        
        # ============================================

        existing_apps_data = list(
            Application.objects.filter(
                application_date=app_date
            ).values_list('applicant_id', 'program_id')
        )
        
        # Создаём словарь program_id -> program_code
        program_id_to_code = {prog.id: prog.code for prog in programs_cache.values()}
        
        # Создаём set ключей
        existing_keys = {
            (applicant_id, program_id_to_code.get(program_id))
            for applicant_id, program_id in existing_apps_data
            if program_id_to_code.get(program_id)
        }
        
        # Собираем новые ключи
        new_keys = {
            (app['applicant_id'], app['program'].code)
            for app in new_applications
        }
        
        # Определяем какие заявления нужно удалить
        keys_to_delete = existing_keys - new_keys
        
        # ============================================

        if keys_to_delete:
            # Создаём словарь program_code -> program_id
            program_code_to_id = {prog.code: prog.id for prog in programs_cache.values()}
            
            # Формируем пары (applicant_id, program_id) для удаления
            delete_pairs = [
                (applicant_id, program_code_to_id[program_code])
                for applicant_id, program_code in keys_to_delete
                if program_code in program_code_to_id
            ]
            
            if delete_pairs:
                # Разделяем на списки applicant_id и program_id
                applicant_ids = [pair[0] for pair in delete_pairs]
                program_ids = [pair[1] for pair in delete_pairs]
                
                with connection.cursor() as cursor:
                    # Удаляем одним запросом используя unnest
                    cursor.execute("""
                        DELETE FROM applications
                        WHERE application_date = %s
                        AND (applicant_id, program_id) IN (
                            SELECT * FROM unnest(%s::int[], %s::int[])
                        )
                    """, [app_date, applicant_ids, program_ids])
                    
                    deleted_count = cursor.rowcount
                
                stats['applications_deleted'] += deleted_count
                logger.info(f"[-] Удалено устаревших заявлений: {deleted_count}")
        
        # Определяем новые заявления
        apps_to_create = [
            app for app in new_applications
            if (app['applicant_id'], app['program'].code) not in existing_keys
        ]
        
        if not apps_to_create:
            logger.info(f"[i] Нет новых заявлений для {app_date}")
            return
        
        # Получаем абитуриентов
        applicant_ids_needed = {app['applicant_id'] for app in apps_to_create}
        applicants_map = Applicant.objects.in_bulk(
            applicant_ids_needed,
            field_name='applicant_id'
        )
        
        # Создаем заявления
        applications_objects = []
        for app_data in apps_to_create:
            applicant = applicants_map.get(app_data['applicant_id'])
            if not applicant:
                logger.warning(f"[!] Абитуриент {app_data['applicant_id']} не найден")
                continue
            
            applications_objects.append(Application(
                applicant=applicant,
                program=app_data['program'],
                priority=app_data['priority'],
                consent=app_data['consent'],
                application_date=app_date,
            ))
        
        # Bulk create
        if applications_objects:
            Application.objects.bulk_create(
                applications_objects,
                batch_size=DBUpdater.BATCH_SIZE,
                ignore_conflicts=True
            )
            stats['applications_created'] += len(applications_objects)
            logger.info(f"[+] Создано заявлений: {len(applications_objects)}")
            
            # Статистика по программам
            for app in applications_objects:
                prog_code = app.program.code
                date_str = str(app_date)
                
                if date_str not in stats['programs_stats'][prog_code]:
                    stats['programs_stats'][prog_code][date_str] = {
                        'total': 0,
                        'with_consent': 0
                    }
                
                stats['programs_stats'][prog_code][date_str]['total'] += 1
                if app.consent:
                    stats['programs_stats'][prog_code][date_str]['with_consent'] += 1
    
    @staticmethod
    @transaction.atomic
    def update_database(parsed_files: List[Dict]) -> Dict:
        """
        Главный метод обновления БД
        ФИНАЛЬНАЯ ВЕРСИЯ - RAW SQL DELETE для предотвращения взрыва памяти
        """
        start_time = time.time()
        
        logger.info("=" * 60)
        logger.info("НАЧАЛО ОПТИМИЗИРОВАННОГО ОБНОВЛЕНИЯ БД")
        logger.info("=" * 60)
        
        # Инициализация статистики
        stats = {
            'total_files': len(parsed_files),
            'total_records': sum(f['records_count'] for f in parsed_files),
            'applicants_created': 0,
            'applicants_updated': 0,
            'applications_created': 0,
            'applications_deleted': 0,
            'programs_stats': defaultdict(dict)
        }
        
        # Получаем кэш программ
        programs_cache = DBUpdater._get_programs_cache()
        
        # Собираем данные из всех файлов
        (
            all_applicant_data,
            applications_by_date,
            dates_set,
            applicant_ids_set
        ) = DBUpdater._collect_data(parsed_files, programs_cache)
        
        # Создаем/обновляем абитуриентов
        DBUpdater._upsert_applicants(
            all_applicant_data,
            applicant_ids_set,
            stats
        )
        
        # Обрабатываем заявления для каждой даты
        for app_date in sorted(dates_set):
            new_applications = applications_by_date.get(app_date, [])
            DBUpdater._update_applications_for_date(
                app_date,
                new_applications,
                applicant_ids_set,
                programs_cache,
                stats
            )
        
        # Итоговая статистика
        elapsed_time = time.time() - start_time
        
        logger.info("=" * 60)
        logger.info(f"ОБНОВЛЕНИЕ ЗАВЕРШЕНО ЗА {elapsed_time:.2f} СЕКУНД")
        logger.info(
            f"Абитуриентов создано: {stats['applicants_created']}, "
            f"обновлено: {stats['applicants_updated']}"
        )
        logger.info(
            f"Заявлений создано: {stats['applications_created']}, "
            f"удалено: {stats['applications_deleted']}"
        )
        logger.info("=" * 60)
        
        return stats