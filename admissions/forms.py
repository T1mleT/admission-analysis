"""
Формы для загрузки конкурсных списков
"""
from django import forms
from django.core.exceptions import ValidationError


class CSVUploadForm(forms.Form):
    """
    Форма для загрузки CSV файлов с конкурсными списками
    """
    
    # Простое поле без указания виджета
    csv_files = forms.FileField(
        label='Выберите CSV файлы',
        help_text='Можно загрузить несколько файлов одновременно',
        required=True
    )
    
    def clean_csv_files(self):
        """Валидация загруженных файлов"""
        files = self.files.getlist('csv_files')
        
        if not files:
            raise ValidationError('Необходимо выбрать хотя бы один файл')
        
        # Проверяем количество файлов
        if len(files) > 20:
            raise ValidationError('Можно загрузить максимум 20 файлов за раз')
        
        # Проверяем каждый файл
        for file in files:
            # Проверка расширения
            if not file.name.endswith('.csv'):
                raise ValidationError(
                    f'Файл {file.name} имеет неверное расширение. '
                    f'Ожидается .csv'
                )
            
            # Проверка размера (максимум 10 MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError(
                    f'Файл {file.name} слишком большой. '
                    f'Максимальный размер: 10 MB'
                )
            
            # Проверка формата имени файла
            filename = file.name.replace('.csv', '')
            parts = filename.split('_')
            
            if len(parts) != 3:
                raise ValidationError(
                    f'Неверный формат имени файла: {file.name}. '
                    f'Ожидается формат: ПРОГРАММА_ДД_ММ.csv (например, PM_01_08.csv)'
                )
            
            program_code, day, month = parts
            
            # Проверка кода программы
            valid_programs = ['PM', 'IVT', 'ITSS', 'IB']
            if program_code not in valid_programs:
                raise ValidationError(
                    f'Неверный код программы в файле {file.name}. '
                    f'Допустимые коды: {", ".join(valid_programs)}'
                )
            
            # Проверка даты
            try:
                day_int = int(day)
                month_int = int(month)
                
                if not (1 <= day_int <= 31):
                    raise ValueError('День вне диапазона')
                if not (1 <= month_int <= 12):
                    raise ValueError('Месяц вне диапазона')
                    
            except ValueError as e:
                raise ValidationError(
                    f'Неверная дата в имени файла {file.name}: {str(e)}'
                )
        
        return files