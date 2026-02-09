"""
Команда для очистки данных из базы
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone

from applicants.models import Applicant
from admissions.models import Application, UploadHistory, Program


class Command(BaseCommand):
    help = 'Очистка данных из базы с возможностью сброса ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Удалить ВСЁ включая программы',
        )
        parser.add_argument(
            '--with-history',
            action='store_true',
            help='Удалить также историю загрузок',
        )
        parser.add_argument(
            '--reset-ids',
            action='store_true',
            help='Сбросить ID (sequences) к 1',
        )
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Не запрашивать подтверждение',
        )

    def handle(self, *args, **options):
        delete_all = options['all']
        delete_history = options['with_history']
        reset_ids = options['reset_ids']
        no_input = options['no_input']
        
        # Подсчитываем записи
        apps_count = Application.objects.count()
        applicants_count = Applicant.objects.count()
        history_count = UploadHistory.objects.count()
        programs_count = Program.objects.count()
        
        self.stdout.write(self.style.WARNING(
            f"\nТекущее состояние базы данных:\n"
            f"  • Абитуриенты: {applicants_count}\n"
            f"  • Заявления: {apps_count}\n"
            f"  • История загрузок: {history_count}\n"
            f"  • Программы: {programs_count}\n"
        ))
        
        # Формируем сообщение
        actions = []
        if delete_all:
            actions.append("ВСЕ данные включая программы")
        else:
            actions.append("заявления и абитуриенты")
        
        if delete_history:
            actions.append("история загрузок")
        elif not delete_all:
            actions.append("история загрузок СОХРАНИТСЯ")
        
        if reset_ids:
            actions.append("ID будут сброшены к 1")
        
        message = " | ".join(actions)
        
        self.stdout.write(self.style.WARNING(f"\n{message.upper()}\n"))
        
        # Запрос подтверждения
        if not no_input:
            confirm = input("Продолжить? (yes/no): ")
            if confirm.lower() not in ['yes', 'y', 'да', 'д']:
                self.stdout.write(self.style.ERROR('Отменено'))
                return
        
        try:
            with transaction.atomic():
                # 1. Удаляем заявления
                deleted_apps = Application.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Заявления удалены: {deleted_apps}'))
                
                # 2. Удаляем абитуриентов
                deleted_applicants = Applicant.objects.all().delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Абитуриенты удалены: {deleted_applicants}'))
                
                # 3. История загрузок - опционально
                if delete_history:
                    deleted_history = UploadHistory.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'История загрузок удалена: {deleted_history}'))
                else:
                    self.stdout.write(self.style.WARNING('История загрузок сохранена'))
                
                # 4. Программы - только если --all
                if delete_all:
                    deleted_programs = Program.objects.all().delete()[0]
                    self.stdout.write(self.style.SUCCESS(f'Программы удалены: {deleted_programs}'))
                
                # 5. Сброс ID (sequences)
                if reset_ids:
                    self._reset_sequences(delete_all, delete_history)
            
            self.stdout.write(self.style.SUCCESS(
                f"\nБаза данных очищена успешно!\n"
            ))
            
            if delete_all:
                self.stdout.write(self.style.WARNING(
                    "Не забудьте восстановить программы:\n"
                    "   python manage.py init_programs\n"
                ))
            
            if reset_ids:
                self.stdout.write(self.style.SUCCESS(
                    "ID сброшены. Следующие записи начнутся с ID=1\n"
                ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {str(e)}'))
    
    def _reset_sequences(self, reset_programs=False, reset_history=False):
        """Сброс sequences (автоинкремент ID) в PostgreSQL"""
        with connection.cursor() as cursor:
            # Сбрасываем ID для абитуриентов
            cursor.execute("ALTER SEQUENCE applicants_id_seq RESTART WITH 1;")
            self.stdout.write(self.style.SUCCESS('  ID абитуриентов → 1'))
            
            # Сбрасываем ID для заявлений
            cursor.execute("ALTER SEQUENCE applications_id_seq RESTART WITH 1;")
            self.stdout.write(self.style.SUCCESS('  ID заявлений → 1'))
            
            # Сбрасываем ID для истории загрузок (опционально)
            if reset_history:
                cursor.execute("ALTER SEQUENCE upload_history_id_seq RESTART WITH 1;")
                self.stdout.write(self.style.SUCCESS('  ID истории загрузок → 1'))
            
            # Сбрасываем ID для программ (только если --all)
            if reset_programs:
                cursor.execute("ALTER SEQUENCE programs_id_seq RESTART WITH 1;")
                self.stdout.write(self.style.SUCCESS('  ID программ → 1'))