from django.core.management.base import BaseCommand
from admissions.models import Program


class Command(BaseCommand):
    help = 'Инициализация образовательных программ'

    def handle(self, *args, **options):
        programs = [
            {'code': 'PM', 'name': 'Прикладная математика', 'seats': 40},
            {'code': 'IVT', 'name': 'Информатика и вычислительная техника', 'seats': 50},
            {'code': 'ITSS', 'name': 'Инфокоммуникационные технологии и системы связи', 'seats': 30},
            {'code': 'IB', 'name': 'Информационная безопасность', 'seats': 20},
        ]
        
        for prog_data in programs:
            program, created = Program.objects.get_or_create(
                code=prog_data['code'],
                defaults={
                    'name': prog_data['name'],
                    'seats': prog_data['seats']
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Создана программа: {program.code} - {program.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Программа уже существует: {program.code}')
                )