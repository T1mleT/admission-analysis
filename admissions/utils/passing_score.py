"""
Утилиты для расчета проходного балла с учетом приоритетов
"""
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import date
from django.db.models import Q, Prefetch

from admissions.models import Program, Application
from applicants.models import Applicant

logger = logging.getLogger(__name__)


class PassingScoreCalculator:
    """
    Класс для расчета проходного балла на образовательные программы
    с учетом приоритетов абитуриентов
    """
    
    def __init__(self, application_date: date):
        """
        Инициализация калькулятора
        """
        self.application_date = application_date
        self.enrolled_applicants: Set[int] = set()  # ID зачисленных абитуриентов
        
        logger.info(f"Инициализирован калькулятор для даты: {application_date}")
    
    
    def calculate_all_programs(self) -> Dict[str, Dict]:
        """
        Рассчитывает проходные баллы для всех программ
        """

        logger.info("Начало расчета проходных баллов")

        # Сбрасываем список зачисленных
        self.enrolled_applicants = set()

        # Получаем все программы
        programs = {p.code: p for p in Program.objects.all()}

        # Инициализируем результаты для каждой программы
        results = {}
        for code, program in programs.items():
            results[code] = {
                'program_code': code,
                'program_name': program.name,
                'total_seats': program.seats,
                'passing_score': "НЕДОБОР",
                'enrolled_count': 0,
                'enrolled_list': [],
                'stats_by_priority': {1: 0, 2: 0, 3: 0, 4: 0},
                'has_shortage': True,
                'applications_total': 0,
                'applications_with_consent': 0,
            }

        # Получаем всех абитуриентов с согласием, отсортированных по баллам
        applications_with_consent = Application.objects.filter(
            application_date=self.application_date,
            consent=True
        ).select_related('applicant', 'program').order_by(
            '-applicant__total_score',  # Сначала высокие баллы
            'applicant__applicant_id'   # Стабильная сортировка
        )

        # Группируем заявления по абитуриентам
        applicants_applications = {}
        for app in applications_with_consent:
            applicant_id = app.applicant.applicant_id
            if applicant_id not in applicants_applications:
                applicants_applications[applicant_id] = {
                    'applicant': app.applicant,
                    'applications': []
                }
            applicants_applications[applicant_id]['applications'].append(app)

        logger.info(f"Всего абитуриентов с согласием: {len(applicants_applications)}")

        # ГЛАВНЫЙ АЛГОРИТМ: обрабатываем абитуриентов от высших баллов к низшим
        for applicant_id, data in sorted(
            applicants_applications.items(),
            key=lambda x: (-x[1]['applicant'].total_score, x[0])
        ):
            if applicant_id in self.enrolled_applicants:
                continue  # Уже зачислен
            
            applicant = data['applicant']
            applications = data['applications']

            # Сортируем заявления по приоритетам (1, 2, 3, 4)
            applications.sort(key=lambda app: app.priority)

            # Пытаемся зачислить на программу с наивысшим приоритетом
            for app in applications:
                program_code = app.program.code
                program_result = results[program_code]

                # Есть ли свободные места?
                if program_result['enrolled_count'] < program_result['total_seats']:
                    # Зачисляем
                    program_result['enrolled_list'].append({
                        'applicant_id': applicant_id,
                        'total_score': applicant.total_score,
                        'priority': app.priority,
                        'physics_ict': applicant.physics_ict_score,
                        'russian': applicant.russian_score,
                        'math': applicant.math_score,
                        'achievements': applicant.achievements_score,
                    })
                    program_result['enrolled_count'] += 1
                    program_result['stats_by_priority'][app.priority] += 1

                    self.enrolled_applicants.add(applicant_id)

                    logger.debug(
                        f"Зачислен: ID={applicant_id}, баллы={applicant.total_score}, "
                        f"программа={program_code}, приоритет={app.priority}"
                    )
                    break  # Зачислен, выходим из цикла
                
        # Определяем проходные баллы и добавляем общую статистику
        for program_code, program_result in results.items():
            program = programs[program_code]

            # Общая статистика
            all_apps = Application.objects.filter(
                program=program,
                application_date=self.application_date
            )
            program_result['applications_total'] = all_apps.count()
            program_result['applications_with_consent'] = all_apps.filter(consent=True).count()

            # Статистика по приоритетам (все заявления)
            program_result['priority_counts'] = {}
            for priority in [1, 2, 3, 4]:
                program_result['priority_counts'][priority] = all_apps.filter(
                    priority=priority
                ).count()

            # Проходной балл
            enrolled_count = program_result['enrolled_count']
            has_shortage = enrolled_count < program.seats

            if enrolled_count == 0:
                passing_score = "НЕДОБОР"
            elif has_shortage:
                passing_score = "НЕДОБОР"
            else:
                # Проходной балл = балл последнего зачисленного
                passing_score = program_result['enrolled_list'][-1]['total_score']

            program_result['passing_score'] = passing_score
            program_result['has_shortage'] = has_shortage

            # Добавляем enrolled_priority_counts для PDF
            program_result['enrolled_priority_counts'] = program_result['stats_by_priority']

            logger.info(
                f"{program_code}: зачислено={enrolled_count}/{program.seats}, "
                f"проходной балл={passing_score}"
            )

        logger.info(f"Расчет завершен для {len(results)} программ")

        return results


def calculate_passing_scores_for_date(
    application_date: date
) -> Dict[str, Dict]:
    """
    Функция для расчета проходных баллов на дату
    """
    calculator = PassingScoreCalculator(application_date)
    return calculator.calculate_all_programs()


def get_passing_score_history() -> List[Dict]:
    """
    Получает историю проходных баллов по всем датам
    """
    
    # Получаем все уникальные даты
    dates = Application.objects.values_list(
        'application_date', 
        flat=True
    ).distinct().order_by('application_date')
    
    history = []
    
    for app_date in dates:
        results = calculate_passing_scores_for_date(app_date)
        history.append({
            'date': app_date,
            'programs': results
        })
    
    return history


def get_applicant_chances(
    applicant_id: int,
    application_date: date
) -> Dict[str, any]:
    """
    Рассчитывает шансы конкретного абитуриента на поступление
    """
    
    try:
        applicant = Applicant.objects.get(applicant_id=applicant_id)
    except Applicant.DoesNotExist:
        raise ValueError(f"Абитуриент {applicant_id} не найден")
    
    # Получаем заявления абитуриента
    applications = Application.objects.filter(
        applicant=applicant,
        application_date=application_date
    ).select_related('program').order_by('priority')
    
    if not applications.exists():
        return {
            'applicant_id': applicant_id,
            'total_score': applicant.total_score,
            'applications': [],
            'message': 'Абитуриент не подавал заявлений на эту дату'
        }
    
    # Рассчитываем проходные баллы
    calculator = PassingScoreCalculator(application_date)
    passing_scores = calculator.calculate_all_programs()
    
    chances = []
    
    for app in applications:
        program_code = app.program.code
        program_results = passing_scores.get(program_code, {})
        passing_score = program_results.get('passing_score')
        
        # Определяем статус
        if passing_score == "НЕДОБОР":
            status = "ЗАЧИСЛЕН" if app.consent else "ЗАЧИСЛЕН БЕЗ СОГЛАСИЯ"
            chance = "Гарантировано"
        elif isinstance(passing_score, int):
            if applicant.total_score > passing_score:
                status = "ЗАЧИСЛЕН" if app.consent else "ВЕРОЯТНО ЗАЧИСЛЕН"
                chance = "Высокая"
            elif applicant.total_score == passing_score:
                status = "НА ГРАНИЦЕ"
                chance = "Средняя"
            else:
                status = "НЕ ЗАЧИСЛЕН"
                chance = "Низкая"
        else:
            status = "НЕИЗВЕСТНО"
            chance = "Неизвестно"
        
        chances.append({
            'program_code': program_code,
            'program_name': app.program.name,
            'priority': app.priority,
            'consent': app.consent,
            'passing_score': passing_score,
            'applicant_score': applicant.total_score,
            'difference': (
                applicant.total_score - passing_score 
                if isinstance(passing_score, int) 
                else None
            ),
            'status': status,
            'chance': chance,
        })
    
    return {
        'applicant_id': applicant_id,
        'total_score': applicant.total_score,
        'applications': chances,
    }