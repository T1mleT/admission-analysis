
"""
Скрипт генерации конкурсных списков (ФИНАЛЬНАЯ ВЕРСИЯ v3.0)
Корректная обработка пересечений множеств
"""

import csv
import random
import os
from typing import Dict, Set, List, Tuple

# ============================================================================
# КОНСТАНТЫ
# ============================================================================

PROGRAMS = ['PM', 'IVT', 'ITSS', 'IB']

PROGRAM_NAMES = {
    'PM': 'Прикладная математика',
    'IVT': 'Информатика и вычислительная техника',
    'ITSS': 'Инфокоммуникационные технологии и системы связи',
    'IB': 'Информационная безопасность'
}

SEATS = {'PM': 40, 'IVT': 50, 'ITSS': 30, 'IB': 20}

APPLICANT_COUNTS = {
    '01.08': {'PM': 60, 'IVT': 100, 'ITSS': 50, 'IB': 70},
    '02.08': {'PM': 380, 'IVT': 370, 'ITSS': 350, 'IB': 260},
    '03.08': {'PM': 1000, 'IVT': 1150, 'ITSS': 1050, 'IB': 800},
    '04.08': {'PM': 1240, 'IVT': 1390, 'ITSS': 1240, 'IB': 1190},
}

SCORE_RANGES = {
    'physics_ict': (45, 100),
    'russian': (45, 100),
    'math': (45, 100),
    'achievements': (0, 10),
}

OUTPUT_DIR = 'data'
CURRENT_ID = 1

# ============================================================================
# КЛАСС АБИТУРИЕНТА
# ============================================================================

class Applicant:
    def __init__(self, applicant_id: int):
        self.id = applicant_id
        self.physics_ict = random.randint(*SCORE_RANGES['physics_ict'])
        self.russian = random.randint(*SCORE_RANGES['russian'])
        self.math = random.randint(*SCORE_RANGES['math'])
        self.achievements = random.randint(*SCORE_RANGES['achievements'])
        self.total_score = self.physics_ict + self.russian + self.math + self.achievements
        self.programs = []
        self.priorities = {}
        self.consents = {}
    
    def add_program(self, program: str, priority: int, consent: bool):
        if program not in self.programs:
            self.programs.append(program)
        self.priorities[program] = priority
        self.consents[program] = consent
    
    def mutate_scores(self):
        self.physics_ict = max(45, min(100, self.physics_ict + random.randint(-5, 5)))
        self.russian = max(45, min(100, self.russian + random.randint(-5, 5)))
        self.math = max(45, min(100, self.math + random.randint(-5, 5)))
        self.achievements = max(0, min(10, self.achievements + random.randint(-2, 2)))
        self.total_score = self.physics_ict + self.russian + self.math + self.achievements

# ============================================================================
# ФУНКЦИИ
# ============================================================================

def get_next_id() -> int:
    global CURRENT_ID
    result = CURRENT_ID
    CURRENT_ID += 1
    return result


def generate_first_day_smart():
    """
    УМНАЯ генерация для 01.08 с пропорциональными пересечениями
    """
    
    program_sets = {prog: set() for prog in PROGRAMS}
    all_applicants = {}
    
    # Целевые числа
    targets = APPLICANT_COUNTS['01.08']
    
    # Вероятности подачи на несколько программ (подбираем эмпирически)
    # Большинство подает на 1-2 программы
    multi_program_probs = {
        1: 0.60,  # 60% только на одну программу
        2: 0.25,  # 25% на две программы
        3: 0.10,  # 10% на три программы
        4: 0.05,  # 5% на все четыре
    }
    
    # Генерируем абитуриентов
    for prog in PROGRAMS:
        target = targets[prog]
        current_count = len(program_sets[prog])
        
        while current_count < target:
            # Определяем, на сколько программ подаст этот абитуриент
            num_programs = random.choices(
                population=[1, 2, 3, 4],
                weights=[
                    multi_program_probs[1],
                    multi_program_probs[2],
                    multi_program_probs[3],
                    multi_program_probs[4]
                ]
            )[0]
            
            # Если на 1 программу - создаем уникального
            if num_programs == 1:
                applicant = Applicant(get_next_id())
                all_applicants[applicant.id] = applicant
                program_sets[prog].add(applicant)
                current_count += 1
            
            # Если на несколько - выбираем случайные программы (включая текущую)
            else:
                # Гарантируем, что текущая программа включена
                selected_programs = [prog]
                other_programs = [p for p in PROGRAMS if p != prog]
                random.shuffle(other_programs)
                selected_programs.extend(other_programs[:num_programs-1])
                
                # Проверяем, не переполнили ли мы другие программы
                can_add = True
                for p in selected_programs:
                    if len(program_sets[p]) >= targets[p]:
                        can_add = False
                        break
                
                if can_add:
                    applicant = Applicant(get_next_id())
                    all_applicants[applicant.id] = applicant
                    for p in selected_programs:
                        program_sets[p].add(applicant)
                    current_count = len(program_sets[prog])
            
            # Защита от бесконечного цикла
            if len(all_applicants) > sum(targets.values()) * 2:
                break
    
    # Корректировка до точных целевых значений
    for prog in PROGRAMS:
        current = len(program_sets[prog])
        target = targets[prog]
        
        if current < target:
            # Добавляем уникальных
            for _ in range(target - current):
                applicant = Applicant(get_next_id())
                all_applicants[applicant.id] = applicant
                program_sets[prog].add(applicant)
        
        elif current > target:
            # Удаляем лишних (приоритет - те, кто на многих программах)
            applicants_list = list(program_sets[prog])
            # Сортируем по количеству программ (убираем тех, кто на большем числе)
            applicants_list.sort(key=lambda a: len([p for p in PROGRAMS if a in program_sets[p]]), reverse=True)
            
            to_remove = current - target
            for applicant in applicants_list[:to_remove]:
                program_sets[prog].discard(applicant)
    
    return program_sets, all_applicants


def assign_priorities_and_consents(program_sets: Dict[str, Set[Applicant]], 
                                   all_applicants: Dict[int, Applicant],
                                   date: str) -> None:
    """Назначает приоритеты и согласия"""
    
    consent_rates = {
        '01.08': 0.30,
        '02.08': 0.60,
        '03.08': 0.75,
        '04.08': 0.90,
    }
    
    for applicant in all_applicants.values():
        his_programs = [prog for prog, prog_set in program_sets.items() 
                       if applicant in prog_set]
        
        random.shuffle(his_programs)
        
        for priority, prog in enumerate(his_programs, start=1):
            if priority == 1:
                consent = random.random() < consent_rates[date]
            else:
                consent = random.random() < (consent_rates[date] * 0.3)
            
            applicant.add_program(prog, priority, consent)


def create_csv_files(program_sets: Dict[str, Set[Applicant]], date: str) -> None:
    """Создает CSV файлы с валидацией"""
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for prog_code, prog_set in program_sets.items():
        filename = f"{OUTPUT_DIR}/{prog_code}_{date.replace('.', '_')}.csv"
        applicants_list = sorted(list(prog_set), key=lambda x: x.id)
        
        # ВАЛИДАЦИЯ: проверка на дубликаты
        seen_ids = set()
        for applicant in applicants_list:
            if applicant.id in seen_ids:
                raise ValueError(f"ДУБЛИКАТ ID {applicant.id} в {prog_code}!")
            seen_ids.add(applicant.id)
        
        # ВАЛИДАЦИЯ: проверка согласованности баллов
        # (Если абитуриент на нескольких программах, баллы должны совпадать)
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'ID',
                'Согласие_на_зачисление',
                'Приоритет_ОП',
                'Балл_Физика_ИКТ',
                'Балл_Русский',
                'Балл_Математика',
                'Балл_ИД',
                'Сумма_баллов'
            ])
            
            for applicant in applicants_list:
                writer.writerow([
                    applicant.id,
                    applicant.consents.get(prog_code, False),
                    applicant.priorities.get(prog_code, 1),
                    applicant.physics_ict,
                    applicant.russian,
                    applicant.math,
                    applicant.achievements,
                    applicant.total_score
                ])
        
        print(f"{filename} ({len(applicants_list)} записей)")


def apply_daily_changes(previous_sets: Dict[str, Set[Applicant]], 
                       previous_applicants: Dict[int, Applicant],
                       date: str) -> tuple:
    """
    Применяет изменения при переходе на новый день
    """
    
    new_sets = {prog: set() for prog in PROGRAMS}
    new_applicants = {}
    already_mutated = set()  # Отслеживаем, кто уже мутирован
    
    # ============================================
    # ШАГ 1: УДАЛЕНИЕ И СОХРАНЕНИЕ СУЩЕСТВУЮЩИХ
    # ============================================
    
    applicants_to_delete_globally = set()
    
    for prog, prev_set in previous_sets.items():
        target_count = APPLICANT_COUNTS[date][prog]
        prev_list = list(prev_set)
        
        # Удаляем 5-10% (НЕЗАВИСИМО для каждой программы)
        delete_percent = random.uniform(0.05, 0.10)
        delete_count = int(len(prev_list) * delete_percent)
        keep_count = len(prev_list) - delete_count
        
        random.shuffle(prev_list)
        kept_applicants = prev_list[:keep_count]
        deleted_applicants = prev_list[keep_count:]
        
        # Помечаем удаленных (если они не участвуют в других программах)
        for applicant in deleted_applicants:
            # Проверяем, участвует ли он в других программах
            other_programs = [p for p in PROGRAMS if p != prog and applicant in previous_sets[p]]
            if not other_programs:
                applicants_to_delete_globally.add(applicant.id)
        
        # Обновляем баллы ОДИН РАЗ для каждого абитуриента
        for applicant in kept_applicants:
            if applicant.id not in already_mutated:
                applicant.mutate_scores()
                already_mutated.add(applicant.id)
            
            new_sets[prog].add(applicant)
            new_applicants[applicant.id] = applicant
    
    # ============================================
    # ШАГ 2: ДОБАВЛЕНИЕ НОВЫХ АБИТУРИЕНТОВ
    # ============================================
    
    # Подсчитываем, сколько нужно добавить
    needed_counts = {}
    for prog in PROGRAMS:
        target = APPLICANT_COUNTS[date][prog]
        current = len(new_sets[prog])
        needed_counts[prog] = target - current
    
    # Добавляем новых с учетом пересечений
    # (Используем упрощенную логику - большинство только на 1 программу)
    
    for prog in PROGRAMS:
        needed = needed_counts[prog]
        
        if needed > 0:
            # 80% новых абитуриентов только на эту программу
            single_program_count = int(needed * 0.8)
            
            for _ in range(single_program_count):
                new_applicant = Applicant(get_next_id())
                new_sets[prog].add(new_applicant)
                new_applicants[new_applicant.id] = new_applicant
            
            # Остальные 20% могут быть на нескольких программах
            multi_program_count = needed - single_program_count
            
            for _ in range(multi_program_count):
                new_applicant = Applicant(get_next_id())
                
                # Решаем, на сколько программ подать (1-3)
                num_programs = random.choice([1, 2, 3])
                
                # Гарантируем, что текущая программа включена
                selected_programs = [prog]
                
                if num_programs > 1:
                    other_progs = [p for p in PROGRAMS if p != prog and needed_counts[p] > 0]
                    random.shuffle(other_progs)
                    selected_programs.extend(other_progs[:num_programs-1])
                
                # Добавляем на выбранные программы
                for p in selected_programs:
                    new_sets[p].add(new_applicant)
                    # Уменьшаем счетчик нужных для этой программы
                    if p != prog:
                        needed_counts[p] = max(0, needed_counts[p] - 1)
                
                new_applicants[new_applicant.id] = new_applicant
    
    # Финальная корректировка - добираем или убираем лишних
    for prog in PROGRAMS:
        target = APPLICANT_COUNTS[date][prog]
        current = len(new_sets[prog])
        
        if current < target:
            # Добавляем уникальных
            for _ in range(target - current):
                new_applicant = Applicant(get_next_id())
                new_sets[prog].add(new_applicant)
                new_applicants[new_applicant.id] = new_applicant
        
        elif current > target:
            # Удаляем лишних (приоритет - новые абитуриенты)
            applicants_list = list(new_sets[prog])
            # Сортируем: новые (большие ID) в начале
            applicants_list.sort(key=lambda a: a.id, reverse=True)
            
            to_remove = current - target
            for applicant in applicants_list[:to_remove]:
                # Проверяем, не на единственной ли программе он
                other_progs = [p for p in PROGRAMS if p != prog and applicant in new_sets[p]]
                if not other_progs:
                    # Можем безопасно удалить полностью
                    new_sets[prog].discard(applicant)
                    if applicant.id in new_applicants:
                        del new_applicants[applicant.id]
                else:
                    # Только убираем из этой программы
                    new_sets[prog].discard(applicant)
    
    return new_sets, new_applicants


def print_statistics(program_sets: Dict[str, Set[Applicant]], date: str):
    """Выводит статистику"""
    
    print("\nСтатистика:")
    
    # Пересечения
    all_applicants = {}
    for prog, prog_set in program_sets.items():
        for applicant in prog_set:
            if applicant.id not in all_applicants:
                all_applicants[applicant.id] = []
            all_applicants[applicant.id].append(prog)
    
    multi_count = sum(1 for progs in all_applicants.values() if len(progs) > 1)
    
    for prog, prog_set in program_sets.items():
        consents = sum(1 for a in prog_set if a.consents.get(prog, False))
        print(f"  {prog:5} | Всего: {len(prog_set):4} | С согласием: {consents:3} | Мест: {SEATS[prog]:2}")
    
    print(f"\n  Абитуриентов на >1 программу: {multi_count}")


def generate_all_data():
    """Генерирует все данные"""
    
    print("=" * 70)
    print("ГЕНЕРАЦИЯ КОНКУРСНЫХ СПИСКОВ (v3.0 - ФИНАЛЬНАЯ)")
    print("=" * 70)
    print()
    
    dates = ['01.08', '02.08', '03.08', '04.08']
    previous_sets = None
    previous_applicants = None
    
    for i, date in enumerate(dates):
        print(f"Дата: {date}")
        print("-" * 70)
        
        if i == 0:
            program_sets, all_applicants = generate_first_day_smart()
        else:
            program_sets, all_applicants = apply_daily_changes(
                previous_sets, previous_applicants, date
            )
        
        assign_priorities_and_consents(program_sets, all_applicants, date)
        create_csv_files(program_sets, date)
        print_statistics(program_sets, date)
        
        print()
        
        previous_sets = program_sets
        previous_applicants = all_applicants
    
    print("=" * 70)
    print("ГЕНЕРАЦИЯ ЗАВЕРШЕНА!")
    print(f"Файлы: {OUTPUT_DIR}/")
    print(f"Всего: {len(dates) * len(PROGRAMS)} файлов")
    print("=" * 70)


if __name__ == '__main__':
    random.seed(42)
    generate_all_data()