
"""
Скрипт для валидации v2.0

"""

import csv
import os
from collections import defaultdict

OUTPUT_DIR = 'data'
PROGRAMS = ['PM', 'IVT', 'ITSS', 'IB']
DATES = ['01_08', '02_08', '03_08', '04_08']

EXPECTED_COUNTS = {
    '01_08': {'PM': 60, 'IVT': 100, 'ITSS': 50, 'IB': 70},
    '02_08': {'PM': 380, 'IVT': 370, 'ITSS': 350, 'IB': 260},
    '03_08': {'PM': 1000, 'IVT': 1150, 'ITSS': 1050, 'IB': 800},
    '04_08': {'PM': 1240, 'IVT': 1390, 'ITSS': 1240, 'IB': 1190},
}


def validate_files_exist():
    """Проверка наличия всех файлов"""
    print("Проверка наличия файлов...")
    
    missing_files = []
    for date in DATES:
        for prog in PROGRAMS:
            filename = f"{OUTPUT_DIR}/{prog}_{date}.csv"
            if not os.path.exists(filename):
                missing_files.append(filename)
    
    if missing_files:
        print("Отсутствуют файлы:")
        for f in missing_files:
            print(f"   - {f}")
        return False
    else:
        print(f"Все {len(DATES) * len(PROGRAMS)} файлов найдены")
        return True


def validate_counts():
    """Проверка количества записей"""
    print("\nПроверка количества записей...")
    
    all_correct = True
    for date in DATES:
        print(f"\nДата: {date}")
        for prog in PROGRAMS:
            filename = f"{OUTPUT_DIR}/{prog}_{date}.csv"
            
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)
                count = sum(1 for _ in reader)
            
            expected = EXPECTED_COUNTS[date][prog]
            status = "✅" if count == expected else "❌"
            print(f"  {prog:5} | Ожидается: {expected:4} | Фактически: {count:4} {status}")
            
            if count != expected:
                all_correct = False
    
    return all_correct


def validate_intersections(date: str):
    """Проверка пересечений"""
    print(f"\nПроверка пересечений для {date}...")
    
    program_ids = {}
    for prog in PROGRAMS:
        filename = f"{OUTPUT_DIR}/{prog}_{date}.csv"
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            program_ids[prog] = set(int(row['ID']) for row in reader)
    
    print("  Пересечения двух программ:")
    for i, prog1 in enumerate(PROGRAMS):
        for prog2 in PROGRAMS[i+1:]:
            intersection = len(program_ids[prog1] & program_ids[prog2])
            print(f"    {prog1}-{prog2}: {intersection}")
    
    print("  Пересечения трех программ:")
    from itertools import combinations
    for combo in combinations(PROGRAMS, 3):
        intersection = len(program_ids[combo[0]] & program_ids[combo[1]] & program_ids[combo[2]])
        print(f"    {'-'.join(combo)}: {intersection}")
    
    all_four = len(program_ids['PM'] & program_ids['IVT'] & 
                   program_ids['ITSS'] & program_ids['IB'])
    print(f"  Пересечение всех четырех: {all_four}")


def validate_scores():
    """Проверка валидности баллов"""
    print("\nПроверка валидности баллов...")
    
    errors = []
    for date in DATES:
        for prog in PROGRAMS:
            filename = f"{OUTPUT_DIR}/{prog}_{date}.csv"
            
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    applicant_id = row['ID']
                    
                    physics = int(row['Балл_Физика_ИКТ'])
                    russian = int(row['Балл_Русский'])
                    math = int(row['Балл_Математика'])
                    achievements = int(row['Балл_ИД'])
                    total = int(row['Сумма_баллов'])
                    
                    if not (45 <= physics <= 100):
                        errors.append(f"{filename}: ID {applicant_id} - Физика вне диапазона")
                    if not (45 <= russian <= 100):
                        errors.append(f"{filename}: ID {applicant_id} - Русский вне диапазона")
                    if not (45 <= math <= 100):
                        errors.append(f"{filename}: ID {applicant_id} - Математика вне диапазона")
                    if not (0 <= achievements <= 10):
                        errors.append(f"{filename}: ID {applicant_id} - ИД вне диапазона")
                    
                    expected_total = physics + russian + math + achievements
                    if total != expected_total:
                        errors.append(f"{filename}: ID {applicant_id} - Неверная сумма")
    
    if errors:
        print("Найдены ошибки:")
        for err in errors[:10]:
            print(f"   {err}")
        if len(errors) > 10:
            print(f"   ... и еще {len(errors) - 10} ошибок")
        return False
    else:
        print("Все баллы корректны")
        return True


def validate_cross_file_logic():
    """
    Проверка логики между файлами
    (один абитуриент может быть в нескольких файлах - это нормально!)
    """
    print("\nПроверка логики между файлами...")
    
    # Собираем информацию о всех абитуриентах
    applicant_programs = defaultdict(list)  # ID -> [(программа, дата, приоритет)]
    
    for date in DATES:
        for prog in PROGRAMS:
            filename = f"{OUTPUT_DIR}/{prog}_{date}.csv"
            with open(filename, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    applicant_id = int(row['ID'])
                    priority = int(row['Приоритет_ОП'])
                    applicant_programs[applicant_id].append((prog, date, priority))
    
    # Статистика
    multi_program_count = sum(1 for programs in applicant_programs.values() 
                             if len(programs) > 1)
    
    max_programs = max(len(programs) for programs in applicant_programs.values())
    
    print(f"Всего уникальных абитуриентов: {len(applicant_programs)}")
    print(f"Подали на несколько программ: {multi_program_count}")
    print(f"Максимум программ у одного абитуриента: {max_programs}")
    
    # Проверка приоритетов (должны быть уникальными у каждого абитуриента)
    errors = []
    for applicant_id, programs in applicant_programs.items():
        # Группируем по датам
        by_date = defaultdict(list)
        for prog, date, priority in programs:
            by_date[date].append((prog, priority))
        
        # Проверяем уникальность приоритетов в каждую дату
        for date, progs_prios in by_date.items():
            priorities = [p[1] for p in progs_prios]
            if len(priorities) != len(set(priorities)):
                errors.append(f"ID {applicant_id}, дата {date}: дублирующиеся приоритеты")
    
    if errors:
        print("Найдены ошибки в приоритетах:")
        for err in errors[:5]:
            print(f"   {err}")
        return False
    else:
        print("Приоритеты назначены корректно")
        return True


def main():
    """Главная функция"""
    print("=" * 70)
    print("🔬 ВАЛИДАЦИЯ КОНКУРСНЫХ СПИСКОВ (v2.0)")
    print("=" * 70)
    
    checks = [
        ("Наличие файлов", validate_files_exist),
        ("Количество записей", validate_counts),
        ("Валидность баллов", validate_scores),
        ("Логика между файлами", validate_cross_file_logic),
    ]
    
    results = {}
    for name, check_func in checks:
        results[name] = check_func()
    
    # Пересечения для первой даты
    validate_intersections('01_08')
    
    print("\n" + "=" * 70)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 70)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:30} : {status}")
    
    all_passed = all(results.values())
    
    print("=" * 70)
    if all_passed:
        print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
        print("\nПримечание:")
        print("   Один абитуриент может присутствовать в нескольких файлах -")
        print("   это означает, что он подал документы на несколько программ.")
    else:
        print("НЕКОТОРЫЕ ПРОВЕРКИ НЕ ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == '__main__':
    main()