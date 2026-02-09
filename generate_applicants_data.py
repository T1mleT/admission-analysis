"""
Скрипт:
  1) Генерирует 16 CSV (4 ОП × 4 дня) в папку data/
  2) Запускает валидатор и печатает отчёт
  3) Завершает работу с кодом 0 только если все обязательные проверки пройдены
     (п.10 проверяется как предупреждение)
"""

import csv
import os
import random
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

# -----------------------------
# Константы (из ТЗ)
# -----------------------------
PROGRAMS = ["PM", "IVT", "ITSS", "IB"]
SEATS = {"PM": 40, "IVT": 50, "ITSS": 30, "IB": 20}

DATES = ["01.08", "02.08", "03.08", "04.08"]

APPLICANT_COUNTS = {
    "01.08": {"PM": 60, "IVT": 100, "ITSS": 50, "IB": 70},
    "02.08": {"PM": 380, "IVT": 370, "ITSS": 350, "IB": 260},
    "03.08": {"PM": 1000, "IVT": 1150, "ITSS": 1050, "IB": 800},
    "04.08": {"PM": 1240, "IVT": 1390, "ITSS": 1240, "IB": 1190},
}

# Таблицы из ТЗ п.9 (в валидаторе и генераторе трактуются как |пересечения множеств|).
PAIRWISE_INTERSECTION = {
    "01.08": {("PM","IVT"):22, ("PM","ITSS"):17, ("PM","IB"):20, ("IVT","ITSS"):19, ("IVT","IB"):22, ("ITSS","IB"):17},
    "02.08": {("PM","IVT"):190, ("PM","ITSS"):190, ("PM","IB"):150, ("IVT","ITSS"):190, ("IVT","IB"):140, ("ITSS","IB"):120},
    "03.08": {("PM","IVT"):760, ("PM","ITSS"):600, ("PM","IB"):410, ("IVT","ITSS"):750, ("IVT","IB"):460, ("ITSS","IB"):500},
    "04.08": {("PM","IVT"):1090, ("PM","ITSS"):1110, ("PM","IB"):1070, ("IVT","ITSS"):1050, ("IVT","IB"):1040, ("ITSS","IB"):1090},
}
TRIPLE_INTERSECTION = {
    "01.08": {("PM","IVT","ITSS"):5, ("PM","IVT","IB"):5, ("IVT","ITSS","IB"):5, ("PM","ITSS","IB"):5},
    "02.08": {("PM","IVT","ITSS"):70, ("PM","IVT","IB"):70, ("IVT","ITSS","IB"):70, ("PM","ITSS","IB"):70},
    "03.08": {("PM","IVT","ITSS"):500, ("PM","IVT","IB"):260, ("IVT","ITSS","IB"):300, ("PM","ITSS","IB"):250},
    "04.08": {("PM","IVT","ITSS"):1020, ("PM","IVT","IB"):1020, ("IVT","ITSS","IB"):1000, ("PM","ITSS","IB"):1040},
}
FOUR_INTERSECTION = {"01.08": 3, "02.08": 50, "03.08": 200, "04.08": 1000}

OUTPUT_DIR = "data"
RANDOM_SEED = 42


# -----------------------------
# Модель данных
# -----------------------------
@dataclass
class Applicant:
    id: int
    physics_ict: int
    russian: int
    math: int
    achievements: int
    total: int
    membership: Tuple[str, ...]
    programs: Dict[str, Dict[str, object]] = field(default_factory=dict)

    @staticmethod
    def split_total(total: int) -> Tuple[int, int, int, int]:
        """
        Делит total на 3 предмета (40..100) + ИД (0..10) с гарантией корректной суммы.
        """
        ach = random.randint(0, 10)
        # стартовые доли
        phys = int(total * 0.35) + random.randint(-6, 6)
        rus = int(total * 0.25) + random.randint(-6, 6)
        # клип по ограничениям
        phys = max(40, min(100, phys))
        rus = max(40, min(100, rus))
        # математика — остаток
        math = total - phys - rus - ach
        # подправим, если математика выходит из диапазона
        if math < 40:
            deficit = 40 - math
            # уменьшаем phys/rus насколько возможно
            take_p = min(deficit, phys - 40)
            phys -= take_p
            deficit -= take_p
            take_r = min(deficit, rus - 40)
            rus -= take_r
            deficit -= take_r
            math = total - phys - rus - ach
        if math > 100:
            excess = math - 100
            add_p = min(excess, 100 - phys)
            phys += add_p
            excess -= add_p
            add_r = min(excess, 100 - rus)
            rus += add_r
            excess -= add_r
            math = total - phys - rus - ach

        # финальный страховочный клип (на случай экстремальных total)
        phys = max(40, min(100, phys))
        rus = max(40, min(100, rus))
        math = max(40, min(100, math))
        # подгоняем точную сумму через математику (самый гибкий предмет)
        total2 = phys + rus + math + ach
        if total2 != total:
            math = max(40, min(100, math + (total - total2)))
        total2 = phys + rus + math + ach
        # если всё равно не совпало из-за клипа — подгоним phys
        if total2 != total:
            phys = max(40, min(100, phys + (total - total2)))
        total2 = phys + rus + math + ach
        # если и тут не сошлось — подгоним rus
        if total2 != total:
            rus = max(40, min(100, rus + (total - total2)))
        total2 = phys + rus + math + ach
        # на крайний случай — пересоберём в допустимый total2
        if total2 != total:
            total = total2
        return phys, rus, math, ach


# -----------------------------
# Восстановление точных областей (exact regions)
# -----------------------------
def _sorted_tuple(x: Tuple[str, ...]) -> Tuple[str, ...]:
    return tuple(sorted(x))


def compute_exact_region_sizes(date: str) -> Dict[Tuple[str, ...], int]:
    """
    Возвращает размеры 15 непересекающихся областей (exact regions) для 4 множеств:
      4 singles, 6 pairs-only, 4 triples-only, 1 four-way.

    Исходные данные: totals по п.8 + пересечения по п.9 (как |пересечения|).
    """
    totals = APPLICANT_COUNTS[date]
    q = FOUR_INTERSECTION[date]

    # Нормализуем ключи, чтобы не зависеть от порядка в исходных словарях
    pair_map: Dict[Tuple[str, str], int] = {}
    for (a, b), v in PAIRWISE_INTERSECTION[date].items():
        aa, bb = sorted((a, b))
        pair_map[(aa, bb)] = v

    triple_map: Dict[Tuple[str, str, str], int] = {}
    for tri, v in TRIPLE_INTERSECTION[date].items():
        t = _sorted_tuple(tri)
        triple_map[t] = v

    # exact triple-only
    exact_triple: Dict[Tuple[str, ...], int] = {}
    for tri, val in triple_map.items():
        exact_triple[tri] = val - q

    # exact pair-only
    exact_pair: Dict[Tuple[str, ...], int] = {}
    for (a, b), pab in pair_map.items():
        ab = (a, b)
        other = [p for p in PROGRAMS if p not in ab]
        t1 = _sorted_tuple((a, b, other[0]))
        t2 = _sorted_tuple((a, b, other[1]))
        exact_pair[ab] = pab - triple_map[t1] - triple_map[t2] + q

    # exact singles
    exact_single: Dict[Tuple[str, ...], int] = {}
    for p in PROGRAMS:
        pairs = [k for k in exact_pair.keys() if p in k]
        triples = [k for k in exact_triple.keys() if p in k]
        s = totals[p]
        s -= sum(exact_pair[k] for k in pairs)
        s -= sum(exact_triple[k] for k in triples)
        s -= q
        exact_single[(p,)] = s

    regions: Dict[Tuple[str, ...], int] = {}
    regions[tuple(sorted(PROGRAMS))] = q
    regions.update(exact_triple)
    regions.update(exact_pair)
    regions.update(exact_single)

    # sanity: all non-negative
    for k, v in regions.items():
        if v < 0:
            raise ValueError(f"[{date}] negative region size for {k}: {v}")

    # sanity: totals reproduce
    for p in PROGRAMS:
        calc = sum(v for k, v in regions.items() if p in k)
        if calc != totals[p]:
            raise AssertionError(f"[{date}] totals mismatch for {p}: expected {totals[p]}, got {calc}")

    return regions


# -----------------------------
# Генерация (scores, priorities, consents)
# -----------------------------
SCORE_MEANS_BY_DATE = {
    # Подобрано под Испытание №2 (d-e):
    # 03.08: PM/IVT заметно сильнее, ITSS/IB заметно слабее
    # 04.08: рост у всех + порядок проходного PM > IB > IVT > ITSS
    "01.08": {"PM": 245, "IVT": 240, "ITSS": 235, "IB": 242},
    "02.08": {"PM": 272, "IVT": 265, "ITSS": 262, "IB": 270},
    "03.08": {"PM": 290, "IVT": 258, "ITSS": 230, "IB": 234},
    "04.08": {"PM": 309, "IVT": 283, "ITSS": 258, "IB": 300},
}

SCORE_SIGMA_BY_DATE = {"01.08": 10, "02.08": 13, "03.08": 14, "04.08": 11}

# Предпочтения для расстановки приоритетов
PRIORITY_WEIGHTS = {
    "01.08": {"PM": 1.0, "IVT": 1.0, "ITSS": 1.0, "IB": 1.0},
    "02.08": {"PM": 1.05, "IVT": 1.0, "ITSS": 0.95, "IB": 1.0},
    "03.08": {"PM": 1.25, "IVT": 1.20, "ITSS": 0.80, "IB": 0.85},
    "04.08": {"PM": 1.35, "IB": 1.25, "IVT": 1.05, "ITSS": 0.90},
}

# Целевые количества согласий (используются для аккуратной доводки).
CONSENT_TARGETS = {
    "01.08": {"PM": 25, "IVT": 35, "ITSS": 20, "IB": 15},  # меньше мест -> НЕДОБОР
    "02.08": {"PM": 220, "IVT": 240, "ITSS": 210, "IB": 170},
    "03.08": {"PM": 560, "IVT": 660, "ITSS": 160, "IB": 120},  # согласий достаточно, но "сильных" выдавливаем из ITSS/IB
    "04.08": {"PM": 600, "IVT": 520, "ITSS": 220, "IB": 380},  # > мест, IB усиливаем
}



def _clip(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))

def draw_total_score(date: str, membership: Tuple[str, ...]) -> int:
    """
    Абитуриент имеет один общий total, но он должен быть "совместим" с программами.
    Берём максимум из средних по его программам + шум.

    Дополнительно (для стабильного Испытания №2 e):
      - на 04.08 ограничиваем "потолок" для IVT и особенно ITSS, чтобы их проходные были ниже PM/IB.
    """
    means = SCORE_MEANS_BY_DATE[date]
    mu = max(means[p] for p in membership)
    sigma = SCORE_SIGMA_BY_DATE[date]
    base = int(random.gauss(mu, sigma) + (len(membership) - 1) * 3)

    if date == "01.08":
        lo, hi = 200, 275
    elif date == "02.08":
        lo, hi = 210, 290
    elif date == "03.08":
        lo, hi = 200, 292
    else:
        lo, hi = 220, 310
        # caps для 04.08
        # (если абитуриент не имеет PM/IB в наборах, но имеет IVT/ITSS — он не должен быть "слишком сильным")
        if "PM" not in membership and "IB" not in membership:
            if "IVT" in membership:
                hi = min(hi, 306)
            if "ITSS" in membership:
                hi = min(hi, 302)

    return _clip(base, lo, hi)

def assign_priorities(date: str, membership: Tuple[str, ...], total: int) -> Dict[str, int]:
    """
    Приоритеты 1..k для программ в membership.
    Чем выше total, тем сильнее bias на "топовые" программы даты (через веса).
    """
    w = PRIORITY_WEIGHTS[date]
    # усиливаем веса для сильных абитуриентов
    boost = 1.0 + max(0.0, (total - 240) / 120.0) * 0.35  # ~1..1.35
    scored = []
    for p in membership:
        noise = random.uniform(-0.05, 0.05)
        scored.append((-(w[p] * boost + noise), p))
    scored.sort()
    pr = {}
    for i, (_, p) in enumerate(scored, start=1):
        pr[p] = i
    return pr

def initial_consent_prob(date: str, prog: str, priority: int, total: int) -> float:
    """
    Базовая вероятность согласия. Затем мы ещё доводим до целевых количеств.
    """
    if date == "01.08":
        base = 0.18
    elif date == "02.08":
        base = 0.70
    elif date == "03.08":
        base = 0.72
    else:
        base = 0.78

    # согласие чаще у приоритета 1
    base += 0.10 if priority == 1 else (0.04 if priority == 2 else 0.0)

    # сильные чаще дают согласие (слабая зависимость)
    base += (total - 240) / 800.0  # ±0.1

    # небольшая программная поправка для нужных трендов
    if date == "03.08":
        if prog in ("PM", "IVT"):
            base += 0.05
        else:
            base -= 0.06
    if date == "04.08":
        if prog == "PM":
            base += 0.04
        if prog == "IB":
            base += 0.06
        if prog == "IVT":
            base -= 0.03
        if prog == "ITSS":
            base -= 0.06

    return max(0.0, min(0.98, base))

def generate_day(date: str, start_id: int) -> Tuple[Dict[str, List[Applicant]], int]:
    """
    Возвращает:
      - списки по программам {prog: [Applicant,...]}
      - следующий свободный ID
    """
    regions = compute_exact_region_sizes(date)
    applicants_by_id: Dict[int, Applicant] = {}
    next_id = start_id

    # создаём абитуриентов по регионам
    for membership, count in regions.items():
        for _ in range(count):
            aid = next_id
            next_id += 1
            total = draw_total_score(date, membership)
            phys, rus, math, ach = Applicant.split_total(total)
            total2 = phys + rus + math + ach
            app = Applicant(
                id=aid,
                physics_ict=phys,
                russian=rus,
                math=math,
                achievements=ach,
                total=total2,
                membership=membership,
            )
            # приоритеты/согласия по программам membership
            pr_map = assign_priorities(date, membership, app.total)
            for prog in membership:
                pr = pr_map[prog]
                consent = 1 if random.random() < initial_consent_prob(date, prog, pr, app.total) else 0
                app.programs[prog] = {"priority": pr, "consent": consent}

            # Жёсткие правила для стабильного выполнения Испытания №2 (d-e):
            # 03.08: сильные абитуриенты не должны поднимать проходной на ITSS/IB
            if date == "03.08" and app.total >= 275:
                if "ITSS" in app.programs:
                    app.programs["ITSS"]["consent"] = 0
                if "IB" in app.programs:
                    app.programs["IB"]["consent"] = 0
            # 04.08: ITSS — самый низкий проходной; убираем согласия у топовых на ITSS
            # Также ограничиваем согласия у слабых на PM/IB, чтобы проходные были выше.
            if date == "04.08" and app.total >= 295:
                if "ITSS" in app.programs:
                    app.programs["ITSS"]["consent"] = 0
            # слабых на PM не допускаем до согласия, чтобы проходной PM был самым высоким
            if date == "04.08" and "PM" in app.programs and app.total < 302:
                app.programs["PM"]["consent"] = 0
            # 04.08: IB должен быть выше IVT — усиливаем смещение топовых в IB (если есть оба)
            # 04.08: топовые с PM/IB не должны "перетекать" в IVT/ITSS (иначе порядок проходных ломается)
            if date == "04.08" and "PM" in app.programs and app.total >= 290:
                if "IVT" in app.programs:
                    app.programs["IVT"]["consent"] = 0
                if "ITSS" in app.programs:
                    app.programs["ITSS"]["consent"] = 0
                if "IB" in app.programs and app.total >= 300:
                    # самые сильные оставляем только на PM
                    app.programs["IB"]["consent"] = 0
            if date == "04.08" and "IB" in app.programs and app.total >= 285:
                if "IVT" in app.programs:
                    app.programs["IVT"]["consent"] = 0
                if "ITSS" in app.programs:
                    app.programs["ITSS"]["consent"] = 0

            applicants_by_id[aid] = app

    # доводим согласия до целевых (по каждой программе отдельно) — это нужно для стабильного Test2.
    targets = CONSENT_TARGETS[date]
    for prog in PROGRAMS:
        # кандидаты в программе
        cand = [a for a in applicants_by_id.values() if prog in a.programs]
        # текущее согласие
        current = [a for a in cand if a.programs[prog]["consent"] == 1]
        target = targets[prog]

        # если согласий больше — выключаем согласие у "самых слабых" и у приоритета>1 в первую очередь
        if len(current) > target:
            current_sorted = sorted(
                current,
                key=lambda a: (a.programs[prog]["priority"], a.total)  # сначала higher priority number (worse), then lower score
            )
            # выключаем с конца? нам нужно убрать "плохих", так что идём по худшим:
            to_off = len(current) - target
            for a in current_sorted[-to_off:]:
                a.programs[prog]["consent"] = 0

        # если согласий меньше — включаем у сильных и с хорошим приоритетом
        elif len(current) < target:
            non = [a for a in cand if a.programs[prog]["consent"] == 0]
            non_sorted = sorted(non, key=lambda a: (a.programs[prog]["priority"], -a.total))
            to_on = min(len(non_sorted), target - len(current))
            for a in non_sorted[:to_on]:
                a.programs[prog]["consent"] = 1

    
    # Повторно применяем ограничения после доводки согласий до целей
    # (чтобы доводка не "включила обратно" запрещённые согласия).
    if date == "03.08":
        for a in applicants_by_id.values():
            if a.total >= 275:
                if "ITSS" in a.programs:
                    a.programs["ITSS"]["consent"] = 0
                if "IB" in a.programs:
                    a.programs["IB"]["consent"] = 0

    if date == "04.08":
        for a in applicants_by_id.values():
            if "ITSS" in a.programs and a.total >= 295:
                a.programs["ITSS"]["consent"] = 0
            if "PM" in a.programs and a.total < 295:
                a.programs["PM"]["consent"] = 0
            if "IB" in a.programs and a.total < 288:
                a.programs["IB"]["consent"] = 0
            if "PM" in a.programs and a.total >= 290:
                if "IVT" in a.programs:
                    a.programs["IVT"]["consent"] = 0
                if "ITSS" in a.programs:
                    a.programs["ITSS"]["consent"] = 0
                if "IB" in a.programs and a.total >= 300:
                    a.programs["IB"]["consent"] = 0
            if "IB" in a.programs and a.total >= 285:
                if "IVT" in a.programs:
                    a.programs["IVT"]["consent"] = 0
                if "ITSS" in a.programs:
                    a.programs["ITSS"]["consent"] = 0

# формируем списки по программам
    per_prog: Dict[str, List[Applicant]] = {p: [] for p in PROGRAMS}
    for a in applicants_by_id.values():
        for prog in a.membership:
            per_prog[prog].append(a)

    # сортируем (обычно в конкурсных списках сортировка по сумме, но ТЗ не требует; оставим для наглядности)
    for prog in PROGRAMS:
        per_prog[prog] = sorted(per_prog[prog], key=lambda a: a.total, reverse=True)
        # контроль количества
        if len(per_prog[prog]) != APPLICANT_COUNTS[date][prog]:
            raise AssertionError(f"[{date}] count mismatch for {prog}: {len(per_prog[prog])} vs {APPLICANT_COUNTS[date][prog]}")

    return per_prog, next_id


def write_csvs(all_days: Dict[str, Dict[str, List[Applicant]]], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    header = ["ID", "Согласие_на_зачисление", "Приоритет_ОП",
              "Балл_Физика_ИКТ", "Балл_Русский", "Балл_Математика", "Балл_ИД", "Сумма_баллов"]
    for date, per_prog in all_days.items():
        for prog, apps in per_prog.items():
            fn = os.path.join(out_dir, f"{prog}_{date.replace('.','_')}.csv")
            with open(fn, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(header)
                for a in apps:
                    pinfo = a.programs[prog]
                    w.writerow([
                        a.id,
                        int(pinfo["consent"]),
                        int(pinfo["priority"]),
                        a.physics_ict,
                        a.russian,
                        a.math,
                        a.achievements,
                        a.total,
                    ])


# -----------------------------
# Валидатор
# -----------------------------
class Validator:
    def __init__(self, data_dir: str = OUTPUT_DIR):
        self.data_dir = data_dir

    def _load_day(self, date: str) -> Dict[str, List[Dict[str, str]]]:
        res: Dict[str, List[Dict[str, str]]] = {}
        for prog in PROGRAMS:
            fn = os.path.join(self.data_dir, f"{prog}_{date.replace('.','_')}.csv")
            if not os.path.exists(fn):
                raise FileNotFoundError(fn)
            with open(fn, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                res[prog] = list(reader)
        return res

    def validate_structure_and_sums(self) -> bool:
        ok = True
        required = {"ID", "Согласие_на_зачисление", "Приоритет_ОП",
                    "Балл_Физика_ИКТ", "Балл_Русский", "Балл_Математика", "Балл_ИД", "Сумма_баллов"}
        for date in DATES:
            day = self._load_day(date)
            for prog, rows in day.items():
                for r in rows:
                    if set(r.keys()) != required:
                        print(f"[ERROR] {date} {prog}: wrong columns {list(r.keys())}")
                        ok = False
                        continue
                    try:
                        _id = int(r["ID"])
                        cons = int(r["Согласие_на_зачисление"])
                        pr = int(r["Приоритет_ОП"])
                        phys = int(r["Балл_Физика_ИКТ"])
                        rus = int(r["Балл_Русский"])
                        mat = int(r["Балл_Математика"])
                        ach = int(r["Балл_ИД"])
                        total = int(r["Сумма_баллов"])
                    except Exception as e:
                        print(f"[ERROR] {date} {prog}: bad types: {e}")
                        ok = False
                        continue
                    if cons not in (0, 1):
                        print(f"[ERROR] {date} {prog} ID={_id}: consent not 0/1")
                        ok = False
                    if pr < 1 or pr > 4:
                        print(f"[ERROR] {date} {prog} ID={_id}: priority out of range")
                        ok = False
                    if not (0 <= ach <= 10):
                        print(f"[ERROR] {date} {prog} ID={_id}: achievements out of range")
                        ok = False
                    for vname, v in [("phys", phys), ("rus", rus), ("mat", mat)]:
                        if not (40 <= v <= 100):
                            print(f"[ERROR] {date} {prog} ID={_id}: {vname} out of range")
                            ok = False
                    if phys + rus + mat + ach != total:
                        print(f"[ERROR] {date} {prog} ID={_id}: sum mismatch {phys+rus+mat+ach} != {total}")
                        ok = False
        if ok:
            print("[OK] Структура CSV и суммы баллов корректны (ТЗ п.7).")
        return ok

    def validate_counts(self) -> bool:
        ok = True
        for date in DATES:
            day = self._load_day(date)
            for prog in PROGRAMS:
                exp = APPLICANT_COUNTS[date][prog]
                act = len(day[prog])
                if act != exp:
                    print(f"[ERROR] {date} {prog}: expected {exp}, got {act}")
                    ok = False
        if ok:
            print("[OK] Кол-во строк в списках соответствует ТЗ п.8.")
        return ok

    def _sets(self, date: str) -> Dict[str, Set[int]]:
        day = self._load_day(date)
        return {prog: set(int(r["ID"]) for r in rows) for prog, rows in day.items()}

    def validate_intersections(self) -> bool:
        ok = True
        for date in DATES:
            sets = self._sets(date)

            # pairs |A∩B|
            for (a, b), exp in PAIRWISE_INTERSECTION[date].items():
                act = len(sets[a] & sets[b])
                if act != exp:
                    print(f"[ERROR] {date} |{a}∩{b}| expected {exp}, got {act}")
                    ok = False

            # triples |A∩B∩C|
            for tri, exp in TRIPLE_INTERSECTION[date].items():
                a, b, c = tri
                act = len(sets[a] & sets[b] & sets[c])
                if act != exp:
                    print(f"[ERROR] {date} |{a}∩{b}∩{c}| expected {exp}, got {act}")
                    ok = False

            # four
            a, b, c, d = PROGRAMS
            exp4 = FOUR_INTERSECTION[date]
            act4 = len(sets[a] & sets[b] & sets[c] & sets[d])
            if act4 != exp4:
                print(f"[ERROR] {date} |4-way| expected {exp4}, got {act4}")
                ok = False

        if ok:
            print("[OK] Пересечения множеств соответствуют ТЗ п.9 (как мощности пересечений).")
        return ok

    def validate_consents_04(self) -> bool:
        day = self._load_day("04.08")
        ok = True
        for prog in PROGRAMS:
            cons = sum(1 for r in day[prog] if int(r["Согласие_на_зачисление"]) == 1)
            if cons <= SEATS[prog]:
                print(f"[ERROR] 04.08 {prog}: consents {cons} must be > seats {SEATS[prog]}")
                ok = False
        if ok:
            print("[OK] На 04.08 согласий больше, чем мест (ТЗ п.11).")
        return ok

    # ---- Испытание №2: моделирование поступления ----
    def simulate_admission_and_passing(self, date: str) -> Dict[str, Optional[int]]:
        day = self._load_day(date)
        # собираем карточку абитуриента: общий total + его программы
        applicants: Dict[int, Dict[str, object]] = {}
        for prog, rows in day.items():
            for r in rows:
                aid = int(r["ID"])
                if aid not in applicants:
                    applicants[aid] = {"total": int(r["Сумма_баллов"]), "programs": {}}
                applicants[aid]["programs"][prog] = {
                    "priority": int(r["Приоритет_ОП"]),
                    "consent": bool(int(r["Согласие_на_зачисление"]))
                }

        consenting = [(aid, data) for aid, data in applicants.items()
                      if any(p["consent"] for p in data["programs"].values())]
        consenting.sort(key=lambda x: x[1]["total"], reverse=True)

        seats_left = {p: SEATS[p] for p in PROGRAMS}
        admitted: Dict[str, List[Tuple[int, int]]] = {p: [] for p in PROGRAMS}

        for aid, data in consenting:
            prio_list = sorted(data["programs"].items(), key=lambda kv: kv[1]["priority"])
            for prog, pinfo in prio_list:
                if not pinfo["consent"]:
                    continue
                if seats_left[prog] > 0:
                    admitted[prog].append((aid, data["total"]))
                    seats_left[prog] -= 1
                    break

        passing: Dict[str, Optional[int]] = {}
        for p in PROGRAMS:
            if len(admitted[p]) < SEATS[p]:
                passing[p] = None
            else:
                passing[p] = sorted(admitted[p], key=lambda x: x[1])[0][1]  # минимальный среди зачисленных
        return passing

    def validate_test2(self) -> bool:
        ok = True
        p01 = self.simulate_admission_and_passing("01.08")
        for p in PROGRAMS:
            if p01[p] is not None:
                print(f"[ERROR] Test2(b) 01.08 {p}: expected НЕДОБОР, got {p01[p]}")
                ok = False

        p02 = self.simulate_admission_and_passing("02.08")
        for p in PROGRAMS:
            if p02[p] is None:
                print(f"[ERROR] Test2(c) 02.08 {p}: passing should be computable, got НЕДОБОР")
                ok = False

        p03 = self.simulate_admission_and_passing("03.08")
        # d) PM & IVT up, ITSS & IB down vs 02.08
        if not (p03["PM"] > p02["PM"] and p03["IVT"] > p02["IVT"]):
            print(f"[ERROR] Test2(d) expected PM & IVT up: 02={p02}, 03={p03}")
            ok = False
        if not (p03["ITSS"] < p02["ITSS"] and p03["IB"] < p02["IB"]):
            print(f"[ERROR] Test2(d) expected ITSS & IB down: 02={p02}, 03={p03}")
            ok = False

        p04 = self.simulate_admission_and_passing("04.08")
        # e) all up vs 03.08 + order PM > IB > IVT > ITSS
        for p in PROGRAMS:
            if not (p04[p] is not None and p03[p] is not None and p04[p] > p03[p]):
                print(f"[ERROR] Test2(e) expected {p} up: 03={p03[p]}, 04={p04[p]}")
                ok = False
        if not (p04["PM"] > p04["IB"] > p04["IVT"] > p04["ITSS"]):
            print(f"[ERROR] Test2(e) expected order PM>IB>IVT>ITSS, got {p04}")
            ok = False

        if ok:
            print("[OK] Испытание №2 (b–e) пройдено: проходные баллы ведут себя как требуется.")
            print(f"     Passing 01.08: {p01}")
            print(f"     Passing 02.08: {p02}")
            print(f"     Passing 03.08: {p03}")
            print(f"     Passing 04.08: {p04}")
        return ok

    def validate_p10_as_warning(self) -> None:
        # не блокирующая проверка по запросу пользователя
        def day_pairs(date: str) -> Set[Tuple[int, str]]:
            day = self._load_day(date)
            pairs = set()
            for prog, rows in day.items():
                for r in rows:
                    pairs.add((int(r["ID"]), prog))
            return pairs

        for d_prev, d_next in zip(DATES[:-1], DATES[1:]):
            a = day_pairs(d_prev)
            b = day_pairs(d_next)
            removed = len(a - b) / max(1, len(a)) * 100.0
            added = len(b - a) / max(1, len(a)) * 100.0
            print(f"[WARN] p.10 ({d_prev}->{d_next}): removed={removed:.2f}%, added={added:.2f}% (не блокирует)")

    def run_all(self) -> bool:
        ok = True
        ok &= self.validate_structure_and_sums()
        ok &= self.validate_counts()
        ok &= self.validate_intersections()
        ok &= self.validate_consents_04()
        ok &= self.validate_test2()
        self.validate_p10_as_warning()
        return ok


def main() -> None:
    random.seed(RANDOM_SEED)
    all_days: Dict[str, Dict[str, List[Applicant]]] = {}
    next_id = 1
    for date in DATES:
        per_prog, next_id = generate_day(date, next_id)
        all_days[date] = per_prog

    write_csvs(all_days, OUTPUT_DIR)

    print(f"Сгенерировано 16 CSV в папку: {OUTPUT_DIR}/")
    v = Validator(OUTPUT_DIR)
    ok = v.run_all()
    if not ok:
        raise SystemExit(1)
    print("SUCCESS: все обязательные проверки пройдены.")


if __name__ == "__main__":
    main()
