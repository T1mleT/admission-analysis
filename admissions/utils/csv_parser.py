"""
Утилиты для парсинга CSV файлов с конкурсными списками
"""
import csv
import logging
from datetime import datetime
from typing import Dict, List, Tuple
from io import TextIOWrapper

logger = logging.getLogger(__name__)


class CSVParseError(Exception):
    """Исключение для ошибок парсинга CSV"""
    pass


class CSVParser:
    """Парсер CSV файлов конкурсных списков"""
    
    # Ожидаемые заголовки
    EXPECTED_HEADERS = [
        'ID',
        'Согласие_на_зачисление',
        'Приоритет_ОП',
        'Балл_Физика_ИКТ',
        'Балл_Русский',
        'Балл_Математика',
        'Балл_ИД',
        'Сумма_баллов'
    ]
    
    @staticmethod
    def parse_filename(filename: str) -> Tuple[str, datetime.date]:
        """
        Извлекает код программы и дату из имени файла
        """
        try:
            # Убираем расширение
            name_without_ext = filename.replace('.csv', '')
            parts = name_without_ext.split('_')
            
            if len(parts) != 3:
                raise CSVParseError(
                    f'Неверный формат имени файла: {filename}. '
                    f'Ожидается: ПРОГРАММА_ДД_ММ.csv'
                )
            
            program_code, day, month = parts
            
            # Преобразуем в дату (используем 2024 год)
            year = 2024
            date = datetime(year, int(month), int(day)).date()
            
            logger.info(f"Распознан файл: программа={program_code}, дата={date}")
            
            return program_code, date
            
        except ValueError as e:
            raise CSVParseError(f'Ошибка парсинга даты из файла {filename}: {str(e)}')
    
    @staticmethod
    def validate_headers(headers: List[str]) -> bool:
        """
        Проверяет заголовки CSV файла
        """
        if headers != CSVParser.EXPECTED_HEADERS:
            raise CSVParseError(
                f'Некорректные заголовки CSV. '
                f'Ожидается: {CSVParser.EXPECTED_HEADERS}, '
                f'Получено: {headers}'
            )
        return True
    
    @staticmethod
    def parse_boolean(value: str) -> bool:
        """Парсинг булевых значений из CSV"""
        if value in ['True', 'true', '1', 'yes', 'Yes', 'YES']:
            return True
        elif value in ['False', 'false', '0', 'no', 'No', 'NO']:
            return False
        else:
            raise ValueError(f'Некорректное булево значение: {value}')
    
    @staticmethod
    def validate_row(row: Dict[str, str], row_number: int) -> Dict[str, any]:
        """
        Валидация и преобразование строки CSV
        """
        try:
            # Преобразуем и валидируем каждое поле
            data = {
                'applicant_id': int(row['ID']),
                'consent': CSVParser.parse_boolean(row['Согласие_на_зачисление']),
                'priority': int(row['Приоритет_ОП']),
                'physics_ict_score': int(row['Балл_Физика_ИКТ']),
                'russian_score': int(row['Балл_Русский']),
                'math_score': int(row['Балл_Математика']),
                'achievements_score': int(row['Балл_ИД']),
                'total_score': int(row['Сумма_баллов']),
            }
            
            # Валидация диапазонов
            if not (1 <= data['priority'] <= 4):
                raise ValueError(f"Приоритет должен быть от 1 до 4, получено: {data['priority']}")
            
            if not (0 <= data['physics_ict_score'] <= 100):
                raise ValueError(f"Балл Физика/ИКТ вне диапазона: {data['physics_ict_score']}")
            
            if not (0 <= data['russian_score'] <= 100):
                raise ValueError(f"Балл Русский вне диапазона: {data['russian_score']}")
            
            if not (0 <= data['math_score'] <= 100):
                raise ValueError(f"Балл Математика вне диапазона: {data['math_score']}")
            
            if not (0 <= data['achievements_score'] <= 10):
                raise ValueError(f"Балл ИД вне диапазона: {data['achievements_score']}")
            
            # Проверка суммы
            expected_sum = (
                data['physics_ict_score'] + 
                data['russian_score'] + 
                data['math_score'] + 
                data['achievements_score']
            )
            
            if data['total_score'] != expected_sum:
                raise ValueError(
                    f"Неверная сумма баллов. "
                    f"Ожидается: {expected_sum}, указано: {data['total_score']}"
                )
            
            return data
            
        except (ValueError, KeyError) as e:
            raise CSVParseError(
                f'Ошибка в строке {row_number}: {str(e)}'
            )
    
    @staticmethod
    def parse_csv_file(file, filename: str) -> Dict[str, any]:
        """
        Парсит CSV файл полностью
        """
        logger.info(f"Начало парсинга файла: {filename}")
        
        # Извлекаем программу и дату из имени файла
        program_code, date = CSVParser.parse_filename(filename)
        
        # Читаем CSV
        text_file = TextIOWrapper(file, encoding='utf-8')
        reader = csv.DictReader(text_file)
        
        # Проверяем заголовки
        CSVParser.validate_headers(reader.fieldnames)
        
        # Парсим строки
        records = []
        row_count = 0
        
        for row_number, row in enumerate(reader, start=2):  # Начинаем с 2 (1 - заголовок)
            try:
                validated_data = CSVParser.validate_row(row, row_number)
                records.append(validated_data)
                row_count += 1
                
            except CSVParseError as e:
                logger.error(f"Ошибка в файле {filename}: {str(e)}")
                raise
        
        logger.info(
            f"Файл {filename} успешно распарсен. "
            f"Программа: {program_code}, Дата: {date}, Записей: {row_count}"
        )
        
        return {
            'program_code': program_code,
            'date': date,
            'records': records,
            'filename': filename,
            'records_count': row_count
        }