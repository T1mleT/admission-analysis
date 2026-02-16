
"""
Строгий генератор конкурсных списков + валидатор по ТЗ (пункты 5-11)
и испытанию №2 (b-e).

Важно про п.9 ("только двух ОП / только трех или четырех ОП"):
числа в таблице п.9 математически совместимы с п.8 только в трактовке
мощностей пересечений множеств: |A∩B|, |A∩B∩C|, |A∩B∩C∩D|
(т.е. "включая" тех, кто участвует в 3/4 ОП). Буквальная трактовка "ровно только"
приводит к противоречию уже на 01.08.

Скрипт:
- генерирует 16 CSV в папку data/
- затем валидирует ВСЕ условия ТЗ (5-11) и испытание №2 (b-e)
- п.10 проверяется по УНИКАЛЬНЫМ ID между днями (удаление 5-10%, новые >=10%)
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, List, Tuple, Optional, Set

import numpy as np

# -----------------------------
# ТЗ: константы
# -----------------------------
PROGRAMS: List[str] = ["PM", "IVT", "ITSS", "IB"]
SEATS: Dict[str, int] = {"PM": 40, "IVT": 50, "ITSS": 30, "IB": 20}
DAYS: List[str] = ["01.08", "02.08", "03.08", "04.08"]

TOTALS: Dict[str, Dict[str, int]] = {
    "01.08": {"PM": 60, "IVT": 100, "ITSS": 50, "IB": 70},
    "02.08": {"PM": 380, "IVT": 370, "ITSS": 350, "IB": 260},
    "03.08": {"PM": 1000, "IVT": 1150, "ITSS": 1050, "IB": 800},
    "04.08": {"PM": 1240, "IVT": 1390, "ITSS": 1240, "IB": 1190},
}

# Пары: |A∩B|
PAIRS_TBL: Dict[str, Dict[Tuple[str, str], int]] = {
    "01.08": {("PM", "IVT"): 22, ("PM", "ITSS"): 17, ("PM", "IB"): 20, ("IVT", "ITSS"): 19, ("IVT", "IB"): 22, ("ITSS", "IB"): 17},
    "02.08": {("PM", "IVT"): 190, ("PM", "ITSS"): 190, ("PM", "IB"): 150, ("IVT", "ITSS"): 190, ("IVT", "IB"): 140, ("ITSS", "IB"): 120},
    "03.08": {("PM", "IVT"): 760, ("PM", "ITSS"): 600, ("PM", "IB"): 410, ("IVT", "ITSS"): 750, ("IVT", "IB"): 460, ("ITSS", "IB"): 500},
    "04.08": {("PM", "IVT"): 1090, ("PM", "ITSS"): 1110, ("PM", "IB"): 1070, ("IVT", "ITSS"): 1050, ("IVT", "IB"): 1040, ("ITSS", "IB"): 1090},
}

# Тройки: |A∩B∩C| и четверка: |A∩B∩C∩D|
TRIPLES_TBL: Dict[str, Dict[Tuple[str, ...], int]] = {
    "01.08": {("PM", "IVT", "ITSS"): 5, ("PM", "IVT", "IB"): 5, ("IVT", "ITSS", "IB"): 5, ("PM", "ITSS", "IB"): 5, ("PM", "IVT", "ITSS", "IB"): 3},
    "02.08": {("PM", "IVT", "ITSS"): 70, ("PM", "IVT", "IB"): 70, ("IVT", "ITSS", "IB"): 70, ("PM", "ITSS", "IB"): 70, ("PM", "IVT", "ITSS", "IB"): 50},
    "03.08": {("PM", "IVT", "ITSS"): 500, ("PM", "IVT", "IB"): 260, ("IVT", "ITSS", "IB"): 300, ("PM", "ITSS", "IB"): 250, ("PM", "IVT", "ITSS", "IB"): 200},
    "04.08": {("PM", "IVT", "ITSS"): 1020, ("PM", "IVT", "IB"): 1020, ("IVT", "ITSS", "IB"): 1000, ("PM", "ITSS", "IB"): 1040, ("PM", "IVT", "ITSS", "IB"): 1000},
}

HEADERS = ["ID","Согласие_на_зачисление","Приоритет_ОП","Балл_Физика_ИКТ","Балл_Русский","Балл_Математика","Балл_ИД","Сумма_баллов"]

# Параметры баллов (под испытание №2)
BASE_MAP = {"01.08": 210, "02.08": 255, "03.08": 252, "04.08": 285}
BONUS_MAP = {
    "01.08": {"PM": 0, "IVT": 0, "ITSS": 0, "IB": 0},
    "02.08": {"PM": 8, "IVT": 6, "ITSS": 14, "IB": 16},
    "03.08": {"PM": 22, "IVT": 20, "ITSS": -15, "IB": -18},
    "04.08": {"PM": 120, "IVT": 0, "ITSS": -25, "IB": 25},
}

CONSENT_PROB = {"01.08": 0.03, "02.08": 0.35, "03.08": 0.28, "04.08": 0.32}

KEEP_RATIO = 0.92  # п.10: удаление 5-10% по уникальным ID


# -----------------------------
# Модель данных
# -----------------------------
@dataclass
class ApplicantDay:
    id: int
    programs: Tuple[str, ...]          # набор ОП, где он участвует в этот день
    priorities: Dict[str, int]         # приоритет для каждой ОП из programs (1..len(programs))
    consent: bool
    total: int
    comps: Tuple[int, int, int, int]   # физика/ИКТ, русский, математика, ИД


# -----------------------------
# Математика для п.9
# -----------------------------
def _sorted_pair(a: str, b: str) -> Tuple[str, str]:
    return tuple(sorted((a, b), key=lambda x: PROGRAMS.index(x)))  # type: ignore

def compute_exact_regions(day: str) -> Dict[Tuple[str, ...], int]:
    """
    Преобразует инклюзивные пересечения (|A∩B|, |A∩B∩C|, |A∩B∩C∩D|)
    в размеры 15 "точных" областей (ровно в 1/2/3/4 ОП) по inclusion–exclusion.
    """
    q = TRIPLES_TBL[day][tuple(PROGRAMS)]
    triple_inclusive = {k: v for k, v in TRIPLES_TBL[day].items() if len(k) == 3}
    triple_exact = {k: v - q for k, v in triple_inclusive.items()}

    pair_exact: Dict[Tuple[str, str], int] = {}
    for (a, b), v in PAIRS_TBL[day].items():
        s = 0
        for tri, tv in triple_exact.items():
            if a in tri and b in tri:
                s += tv
        pair_exact[(a, b)] = v - s - q

    single_exact: Dict[Tuple[str], int] = {}
    for a in PROGRAMS:
        s_pairs = sum(pair_exact[_sorted_pair(a, b)] for b in PROGRAMS if b != a)
        s_tris = sum(tv for tri, tv in triple_exact.items() if a in tri)
        single_exact[(a,)] = TOTALS[day][a] - s_pairs - s_tris - q

    masks: Dict[Tuple[str, ...], int] = {}
    masks.update(single_exact)
    masks.update(pair_exact)
    masks.update(triple_exact)
    masks[tuple(PROGRAMS)] = q

    if any(v < 0 for v in masks.values()):
        bad = {k: v for k, v in masks.items() if v < 0}
        raise ValueError(f"Negative exact regions for {day}: {bad}")
    return masks


def exact_only_feasibility(day: str) -> bool:
    """
    Проверка, может ли таблица п.9 быть интерпретирована буквально как "ровно только"
    без противоречия с TOTALS (п.8).
    Возвращает True, если не противоречит (на практике для данных из PDF — False).
    """
    # Если "только двух" и "только трех/четырех" трактовать как exact2/exact3/exact4,
    # то для каждой программы total = single + sum(exact2) + sum(exact3) + exact4.
    # Здесь single должен быть >=0.
    q = TRIPLES_TBL[day][tuple(PROGRAMS)]
    # в буквальной трактовке: exact3 = значения столбцов троек (а четверка отдельно)
    exact3 = {k: v for k, v in TRIPLES_TBL[day].items() if len(k) == 3}
    exact2 = {k: v for k, v in PAIRS_TBL[day].items()}
    for a in PROGRAMS:
        s2 = sum(v for (x, y), v in exact2.items() if a in (x, y))
        s3 = sum(v for tri, v in exact3.items() if a in tri)
        single = TOTALS[day][a] - s2 - s3 - q
        if single < 0:
            return False
    return True


# -----------------------------
# Генерация баллов/компонентов
# -----------------------------
def generate_scores(day: str, first_choice: str, rng: np.random.Generator) -> Tuple[int, Tuple[int, int, int, int]]:
    """
    Генерирует компоненты так, чтобы:
    - каждый экзамен 40..100
    - ИД 0..10
    - сумма = total строго
    """
    base = BASE_MAP[day] + BONUS_MAP[day][first_choice]
    desired_total = int(np.clip(rng.normal(base, 16), 150, 310))
    idb = int(np.clip(rng.integers(0, 11), 0, 10))

    # подбираем три компоненты так, чтобы физ/рус/мат в 40..100 и сумма ровно
    remaining = desired_total - idb
    # Если remaining слишком мал/велик для 3 экзаменов, подправим desired_total
    remaining = int(np.clip(remaining, 3 * 40, 3 * 100))
    desired_total = remaining + idb

    for _ in range(200):
        phys = int(rng.integers(40, 101))
        rus = int(rng.integers(40, 101))
        mat = remaining - phys - rus
        if 40 <= mat <= 100:
            total = desired_total
            return total, (phys, rus, mat, idb)

    # fallback (почти не должен срабатывать)
    phys = 80
    rus = 80
    mat = remaining - phys - rus
    mat = int(np.clip(mat, 40, 100))
    # скорректируем phys чтобы сумма совпала
    diff = remaining - (phys + rus + mat)
    phys = int(np.clip(phys + diff, 40, 100))
    total = phys + rus + mat + idb
    return total, (phys, rus, mat, idb)


# -----------------------------
# Формирование дня с п.10 (по ID)
# -----------------------------
def build_day_applicants(
    day: str,
    rng: np.random.Generator,
    prev_ids: Optional[Set[int]],
    next_id_start: int,
    keep_ratio: float = KEEP_RATIO,
) -> Tuple[List[ApplicantDay], Set[int], Set[int], int]:
    masks = compute_exact_regions(day)
    cap = {k: int(v) for k, v in masks.items()}

    kept: Set[int] = set()
    deleted: Set[int] = set()
    if prev_ids:
        prev_list = list(prev_ids)
        rng.shuffle(prev_list)
        keep_n = int(round(len(prev_list) * keep_ratio))
        kept = set(prev_list[:keep_n])
        deleted = set(prev_list[keep_n:])

    mask_list = sorted(cap.keys(), key=lambda t: (len(t), [PROGRAMS.index(x) for x in t]))

    assignment: Dict[int, Tuple[str, ...]] = {}

    kept_list = list(kept)
    rng.shuffle(kept_list)
    for aid in kept_list:
        options = [m for m in mask_list if cap[m] > 0]
        if not options:
            break
        weights = np.array([cap[m] for m in options], dtype=float)
        weights /= weights.sum()
        m = options[int(rng.choice(len(options), p=weights))]
        assignment[aid] = m
        cap[m] -= 1

    current_ids = set(assignment.keys())
    next_id = next_id_start
    if prev_ids:
        next_id = max(next_id, max(prev_ids) + 1)

    for m in mask_list:
        need = cap[m]
        for _ in range(need):
            while next_id in current_ids or (prev_ids and next_id in prev_ids):
                next_id += 1
            assignment[next_id] = m
            current_ids.add(next_id)
            next_id += 1

    applicants: List[ApplicantDay] = []
    for aid, m in assignment.items():
        progs = tuple(m)
        order = list(progs)
        rng.shuffle(order)
        priorities = {p: i + 1 for i, p in enumerate(order)}
        first_choice = order[0]
        total, comps = generate_scores(day, first_choice, rng)
        consent = bool(rng.random() < CONSENT_PROB[day])
        applicants.append(ApplicantDay(aid, progs, priorities, consent, total, comps))

    def ensure_min_consents(min_needed: Dict[str, int]) -> None:
        for p in PROGRAMS:
            cons = [a for a in applicants if a.consent and p in a.programs]
            if len(cons) < min_needed[p]:
                cand = [a for a in applicants if (not a.consent) and p in a.programs]
                cand.sort(key=lambda a: a.total, reverse=True)
                need = min_needed[p] - len(cons)
                for a in cand[:need]:
                    a.consent = True

    if day == "01.08":
        # NEDOBOR: согласий меньше мест по каждой ОП
        for p in PROGRAMS:
            cons = [a for a in applicants if a.consent and p in a.programs]
            if len(cons) >= SEATS[p]:
                rng.shuffle(cons)
                for a in cons[SEATS[p] - 1:]:
                    a.consent = False
    else:
        ensure_min_consents(SEATS)

    if day == "04.08":
        ensure_min_consents({p: SEATS[p] + 5 for p in PROGRAMS})

    return applicants, current_ids, deleted, next_id



# -----------------------------
# Тюнинг баллов под испытание №2 (делает результат устойчивым)
# -----------------------------
def _first_choice(a: ApplicantDay) -> str:
    # программа с приоритетом 1
    for p, pr in a.priorities.items():
        if pr == 1:
            return p
    # fallback
    return list(a.priorities.keys())[0]

def _adjust_total_inplace(a: ApplicantDay, delta: int) -> None:
    """
    Сдвигает суммарный балл на delta, сохраняя:
    - диапазоны физ/рус/мат 40..100
    - ИД 0..10
    - сумма = total
    """
    if delta == 0:
        return
    phys, rus, mat, idb = a.comps
    parts = [phys, rus, mat]
    # попробуем распределить delta по экзаменам
    remaining_delta = delta

    def apply(i: int, d: int) -> int:
        nonlocal parts
        if d > 0:
            add = min(d, 100 - parts[i])
            parts[i] += add
            return add
        else:
            sub = min(-d, parts[i] - 40)
            parts[i] -= sub
            return -sub

    # сначала пробуем по физике, потом математика, потом русский
    for i in [0, 2, 1]:
        if remaining_delta == 0:
            break
        moved = apply(i, remaining_delta)
        remaining_delta -= moved

    # если осталось — используем ИД
    if remaining_delta != 0:
        if remaining_delta > 0:
            add = min(remaining_delta, 10 - idb)
            idb += add
            remaining_delta -= add
        else:
            sub = min(-remaining_delta, idb - 0)
            idb -= sub
            remaining_delta += sub

    # если всё ещё осталось (крайний случай) — просто игнорируем остаток,
    # чтобы не нарушить диапазоны; главное — консистентность суммы.
    a.comps = (parts[0], parts[1], parts[2], idb)
    a.total = parts[0] + parts[1] + parts[2] + idb


def tune_trial2(all_days: Dict[str, List[ApplicantDay]], max_iter: int = 60) -> None:
    """
    Подкручивает totals так, чтобы устойчиво выполнялись условия испытания №2:
    - 01.08: НЕДОБОР по всем
    - 02.08: все считаются
    - 03.08: PM/IVT ↑, ITSS/IB ↓ относительно 02.08
    - 04.08: рост всех относительно 03.08 и порядок PM > IB > IVT > ITSS
    """
    for _ in range(max_iter):
        cuts = {d: assign_seats(all_days[d])[0] for d in DAYS}

        ok = True
        # 01.08 all None
        if any(cuts["01.08"][p] is not None for p in PROGRAMS):
            ok = False

        # 02.08 all not None
        if any(cuts["02.08"][p] is None for p in PROGRAMS):
            ok = False

        # 03.08 all not None and pattern
        if any(cuts["03.08"][p] is None for p in PROGRAMS):
            ok = False
        else:
            if not (cuts["03.08"]["PM"] > cuts["02.08"]["PM"] and cuts["03.08"]["IVT"] > cuts["02.08"]["IVT"]):
                ok = False
            if not (cuts["03.08"]["ITSS"] < cuts["02.08"]["ITSS"] and cuts["03.08"]["IB"] < cuts["02.08"]["IB"]):
                ok = False

        # 04.08 all not None and growth and order
        if any(cuts["04.08"][p] is None for p in PROGRAMS):
            ok = False
        else:
            if not all(cuts["04.08"][p] > cuts["03.08"][p] for p in PROGRAMS):
                ok = False
            if not (cuts["04.08"]["PM"] > cuts["04.08"]["IB"] > cuts["04.08"]["IVT"] > cuts["04.08"]["ITSS"]):
                ok = False

        if ok:
            return

        # --- корректировки (мягкие, только по 03/04) ---
        # если 02.08 не считается для какой-то ОП — добавим баллов тем, у кого приоритет 1 на эту ОП
        for p in PROGRAMS:
            if cuts["02.08"][p] is None:
                for a in all_days["02.08"]:
                    if _first_choice(a) == p:
                        _adjust_total_inplace(a, +6)

        # 03: добиться нужных направлений
        if cuts["03.08"]["ITSS"] is not None and cuts["02.08"]["ITSS"] is not None and cuts["03.08"]["ITSS"] >= cuts["02.08"]["ITSS"]:
            for a in all_days["03.08"]:
                if _first_choice(a) == "ITSS":
                    _adjust_total_inplace(a, -6)
        if cuts["03.08"]["IB"] is not None and cuts["02.08"]["IB"] is not None and cuts["03.08"]["IB"] >= cuts["02.08"]["IB"]:
            for a in all_days["03.08"]:
                if _first_choice(a) == "IB":
                    _adjust_total_inplace(a, -6)
        if cuts["03.08"]["PM"] is not None and cuts["02.08"]["PM"] is not None and cuts["03.08"]["PM"] <= cuts["02.08"]["PM"]:
            for a in all_days["03.08"]:
                if _first_choice(a) == "PM":
                    _adjust_total_inplace(a, +6)
        if cuts["03.08"]["IVT"] is not None and cuts["02.08"]["IVT"] is not None and cuts["03.08"]["IVT"] <= cuts["02.08"]["IVT"]:
            for a in all_days["03.08"]:
                if _first_choice(a) == "IVT":
                    _adjust_total_inplace(a, +6)

        # 04: рост всех
        if all(cuts["04.08"][p] is not None and cuts["03.08"][p] is not None for p in PROGRAMS):
            for p in PROGRAMS:
                if cuts["04.08"][p] <= cuts["03.08"][p]:
                    for a in all_days["04.08"]:
                        if _first_choice(a) == p:
                            _adjust_total_inplace(a, +6)

        # 04: порядок
        if cuts["04.08"]["PM"] is not None and cuts["04.08"]["IB"] is not None and cuts["04.08"]["PM"] <= cuts["04.08"]["IB"]:
            # усилим PM и чуть ослабим IB
            for a in all_days["04.08"]:
                fc = _first_choice(a)
                if fc == "PM":
                    _adjust_total_inplace(a, +8)
                elif fc == "IB":
                    _adjust_total_inplace(a, -4)

        if cuts["04.08"]["IB"] is not None and cuts["04.08"]["IVT"] is not None and cuts["04.08"]["IB"] <= cuts["04.08"]["IVT"]:
            for a in all_days["04.08"]:
                fc = _first_choice(a)
                if fc == "IB":
                    _adjust_total_inplace(a, +6)
                elif fc == "IVT":
                    _adjust_total_inplace(a, -4)

        if cuts["04.08"]["IVT"] is not None and cuts["04.08"]["ITSS"] is not None and cuts["04.08"]["IVT"] <= cuts["04.08"]["ITSS"]:
            for a in all_days["04.08"]:
                fc = _first_choice(a)
                if fc == "IVT":
                    _adjust_total_inplace(a, +6)
                elif fc == "ITSS":
                    _adjust_total_inplace(a, -4)

    raise RuntimeError("Не удалось стабилизировать испытание №2 за max_iter")
# -----------------------------
# Выгрузка CSV (16 файлов)
# -----------------------------
def write_csvs(all_days: Dict[str, List[ApplicantDay]], out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for day, apps in all_days.items():
        for prog in PROGRAMS:
            fn = os.path.join(out_dir, f"{prog}_{day.replace('.','_')}.csv")
            with open(fn, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(HEADERS)
                for a in apps:
                    if prog not in a.programs:
                        continue
                    phys, rus, math, idb = a.comps
                    w.writerow([
                        a.id,
                        1 if a.consent else 0,
                        a.priorities[prog],
                        phys, rus, math, idb,
                        a.total
                    ])


# -----------------------------
# Алгоритм расчёта проходного (испытание №2)
# -----------------------------
def assign_seats(apps: List[ApplicantDay]) -> Tuple[Dict[str, Optional[int]], Dict[str, List[ApplicantDay]]]:
    assigned: Dict[str, List[ApplicantDay]] = {p: [] for p in PROGRAMS}
    assigned_ids: Set[int] = set()

    for pr in range(1, 5):
        for p in PROGRAMS:
            rem = SEATS[p] - len(assigned[p])
            if rem <= 0:
                continue
            candidates = [a for a in apps if a.consent and a.id not in assigned_ids and a.priorities.get(p) == pr]
            candidates.sort(key=lambda a: a.total, reverse=True)
            for a in candidates[:rem]:
                assigned[p].append(a)
                assigned_ids.add(a.id)

    cutoffs: Dict[str, Optional[int]] = {}
    for p in PROGRAMS:
        if len(assigned[p]) < SEATS[p]:
            cutoffs[p] = None
        else:
            cutoffs[p] = min(a.total for a in assigned[p])
    return cutoffs, assigned


# -----------------------------
# Валидатор
# -----------------------------
def load_day_sets(data_dir: str) -> Dict[str, Dict[str, np.ndarray]]:
    """
    Возвращает day->prog->np.ndarray(ids) (без дублей).
    """
    day_prog_ids: Dict[str, Dict[str, np.ndarray]] = {}
    for day in DAYS:
        day_prog_ids[day] = {}
        for prog in PROGRAMS:
            fn = os.path.join(data_dir, f"{prog}_{day.replace('.','_')}.csv")
            if not os.path.exists(fn):
                raise AssertionError(f"Нет файла: {fn}")
            ids = []
            with open(fn, "r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                # columns
                if r.fieldnames != HEADERS:
                    raise AssertionError(f"Неверные заголовки в {fn}: {r.fieldnames}")
                for row in r:
                    _id = int(row["ID"])
                    cons = int(row["Согласие_на_зачисление"])
                    pr = int(row["Приоритет_ОП"])
                    phys = int(row["Балл_Физика_ИКТ"])
                    rus = int(row["Балл_Русский"])
                    mat = int(row["Балл_Математика"])
                    idb = int(row["Балл_ИД"])
                    tot = int(row["Сумма_баллов"])
                    # ranges
                    if cons not in (0, 1):
                        raise AssertionError(f"{fn}: cons not 0/1 for ID={_id}")
                    if not (1 <= pr <= 4):
                        raise AssertionError(f"{fn}: priority out of range for ID={_id}")
                    if tot != phys + rus + mat + idb:
                        raise AssertionError(f"{fn}: sum mismatch for ID={_id}: {tot} vs {phys+rus+mat+idb}")
                    ids.append(_id)
            # no duplicates per list
            if len(ids) != len(set(ids)):
                raise AssertionError(f"{fn}: есть дубликаты ID внутри одного списка")
            day_prog_ids[day][prog] = np.array(sorted(set(ids)), dtype=np.int64)
    return day_prog_ids


def validate_counts_and_intersections(day_prog_ids: Dict[str, Dict[str, np.ndarray]]) -> None:
    # p.8
    for day in DAYS:
        for prog in PROGRAMS:
            n = len(day_prog_ids[day][prog])
            exp = TOTALS[day][prog]
            if n != exp:
                raise AssertionError(f"п.8: {day} {prog}: {n} != {exp}")

    # п.9 пересечения
    for day in DAYS:
        sets = {p: set(day_prog_ids[day][p].tolist()) for p in PROGRAMS}
        # пары
        for (a, b), exp in PAIRS_TBL[day].items():
            got = len(sets[a] & sets[b])
            if got != exp:
                raise AssertionError(f"п.9 пары: {day} {a}-{b}: {got} != {exp}")
        # тройки
        for tri in [("PM", "IVT", "ITSS"), ("PM", "IVT", "IB"), ("IVT", "ITSS", "IB"), ("PM", "ITSS", "IB")]:
            exp = TRIPLES_TBL[day][tri]
            got = len(sets[tri[0]] & sets[tri[1]] & sets[tri[2]])
            if got != exp:
                raise AssertionError(f"п.9 тройки: {day} {tri}: {got} != {exp}")
        # четвёрка
        expq = TRIPLES_TBL[day][tuple(PROGRAMS)]
        gotq = len(sets["PM"] & sets["IVT"] & sets["ITSS"] & sets["IB"])
        if gotq != expq:
            raise AssertionError(f"п.9 четверка: {day}: {gotq} != {expq}")

        _ = compute_exact_regions(day)

    for day in DAYS:
        if exact_only_feasibility(day):
            pass


def validate_p10_by_ids(day_prog_ids: Dict[str, Dict[str, np.ndarray]]) -> None:
    # строим множество ID в БД на каждый день (union всех ОП)
    day_all: Dict[str, Set[int]] = {}
    for day in DAYS:
        s: Set[int] = set()
        for p in PROGRAMS:
            s |= set(day_prog_ids[day][p].tolist())
        day_all[day] = s

    for d_prev, d_cur in zip(DAYS[:-1], DAYS[1:]):
        prev = day_all[d_prev]
        cur = day_all[d_cur]
        deleted = prev - cur
        added = cur - prev
        if len(prev) == 0:
            raise AssertionError("p.10: пустой предыдущий день (неожиданно)")
        del_pct = 100.0 * len(deleted) / len(prev)
        add_pct = 100.0 * len(added) / len(prev)
        if not (5.0 <= del_pct <= 10.0):
            raise AssertionError(f"п.10: {d_prev}->{d_cur}: удалено {del_pct:.2f}% (нужно 5-10%)")
        if not (add_pct >= 10.0):
            raise AssertionError(f"п.10: {d_prev}->{d_cur}: добавлено {add_pct:.2f}% (нужно >=10%)")


def validate_p11_consents(data_dir: str) -> None:
    # 04.08: согласий больше, чем мест (по каждой ОП)
    day = "04.08"
    for prog in PROGRAMS:
        fn = os.path.join(data_dir, f"{prog}_{day.replace('.','_')}.csv")
        cons = 0
        with open(fn, "r", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                cons += int(row["Согласие_на_зачисление"]) == 1
        if cons <= SEATS[prog]:
            raise AssertionError(f"п.11: {prog} 04.08 согласий {cons} <= мест {SEATS[prog]}")


def validate_trial2(data_dir: str) -> None:
    # загружаем applicants per day (по union и восстановлению их программ/приоритетов)
    # Проще: читаем один файл дня, потом собираем по ID из всех ОП.
    for day in DAYS:
        # собрать per-ID: programs set + priority per program + consent + scores
        per_id: Dict[int, dict] = {}
        for prog in PROGRAMS:
            fn = os.path.join(data_dir, f"{prog}_{day.replace('.','_')}.csv")
            with open(fn, "r", encoding="utf-8") as f:
                r = csv.DictReader(f)
                for row in r:
                    _id = int(row["ID"])
                    rec = per_id.setdefault(_id, {
                        "id": _id,
                        "programs": set(),
                        "priorities": {},
                        "consent": int(row["Согласие_на_зачисление"]) == 1,
                        "phys": int(row["Балл_Физика_ИКТ"]),
                        "rus": int(row["Балл_Русский"]),
                        "mat": int(row["Балл_Математика"]),
                        "idb": int(row["Балл_ИД"]),
                        "total": int(row["Сумма_баллов"]),
                    })
                    rec["programs"].add(prog)
                    rec["priorities"][prog] = int(row["Приоритет_ОП"])
                    # consistency
                    if rec["consent"] != (int(row["Согласие_на_зачисление"]) == 1):
                        raise AssertionError(f"{day}: ID {_id} consent differs across lists")
                    if rec["total"] != int(row["Сумма_баллов"]):
                        raise AssertionError(f"{day}: ID {_id} total differs across lists")

        apps: List[ApplicantDay] = []
        for rec in per_id.values():
            apps.append(ApplicantDay(
                id=rec["id"],
                programs=tuple(sorted(rec["programs"], key=lambda x: PROGRAMS.index(x))),
                priorities=rec["priorities"],
                consent=rec["consent"],
                total=rec["total"],
                comps=(rec["phys"], rec["rus"], rec["mat"], rec["idb"]),
            ))

        cutoffs, _assigned = assign_seats(apps)

        if day == "01.08":
            # все НЕДОБОР
            for p in PROGRAMS:
                if cutoffs[p] is not None:
                    raise AssertionError(f"Испытание №2b: {day} {p} не НЕДОБОР (cutoff={cutoffs[p]})")
        elif day == "02.08":
            # все считаются
            for p in PROGRAMS:
                if cutoffs[p] is None:
                    raise AssertionError(f"Испытание №2c: {day} {p} должен считаться, но НЕДОБОР")
            cut02 = cutoffs
        elif day == "03.08":
            for p in PROGRAMS:
                if cutoffs[p] is None:
                    raise AssertionError(f"Испытание №2d: {day} {p} должен считаться, но НЕДОБОР")
            # d: PM,IVT ↑ ; ITSS,IB ↓ относительно 02.08
            if not (cutoffs["PM"] > cut02["PM"] and cutoffs["IVT"] > cut02["IVT"]):
                raise AssertionError(f"Испытание №2d: рост PM/IVT нарушен: 02={cut02}, 03={cutoffs}")
            if not (cutoffs["ITSS"] < cut02["ITSS"] and cutoffs["IB"] < cut02["IB"]):
                raise AssertionError(f"Испытание №2d: падение ITSS/IB нарушено: 02={cut02}, 03={cutoffs}")
            cut03 = cutoffs
        elif day == "04.08":
            for p in PROGRAMS:
                if cutoffs[p] is None:
                    raise AssertionError(f"Испытание №2e: {day} {p} должен считаться, но НЕДОБОР")
            # e: рост всех относительно 03.08
            for p in PROGRAMS:
                if not (cutoffs[p] > cut03[p]):
                    raise AssertionError(f"Испытание №2e: рост {p} нарушен: 03={cut03[p]} 04={cutoffs[p]}")
            # порядок: PM – IB – IVT – ITSS
            if not (cutoffs["PM"] > cutoffs["IB"] > cutoffs["IVT"] > cutoffs["ITSS"]):
                raise AssertionError(f"Испытание №2e: порядок нарушен: {cutoffs}")


def validate_all(data_dir: str) -> None:
    day_prog_ids = load_day_sets(data_dir)
    validate_counts_and_intersections(day_prog_ids)
    validate_p10_by_ids(day_prog_ids)
    validate_p11_consents(data_dir)
    validate_trial2(data_dir)


# -----------------------------
# Main
# -----------------------------
def generate_and_validate(seed: int = 123, out_dir: str | None = None) -> None:
    if out_dir is None:
        out_dir = os.path.join(os.path.dirname(__file__), "data")
    # очистим старые CSV, чтобы не оставалось мусора
    os.makedirs(out_dir, exist_ok=True)
    for name in os.listdir(out_dir):
        if name.lower().endswith(".csv"):
            try:
                os.remove(os.path.join(out_dir, name))
            except OSError:
                pass
    rng = np.random.default_rng(seed)
    all_days: Dict[str, List[ApplicantDay]] = {}
    prev_ids: Optional[Set[int]] = None
    next_id = 1
    for day in DAYS:
        apps, ids, _deleted, next_id = build_day_applicants(day, rng, prev_ids, next_id)
        all_days[day] = apps
        prev_ids = ids

    # стабилизируем условия испытания №2 (b-e)
    tune_trial2(all_days)

    write_csvs(all_days, out_dir)

    # validate
    validate_all(out_dir)

    # печать проходных (для удобства)
    print("SUCCESS: все проверки пройдены.")
    for day in DAYS:
        pass


if __name__ == "__main__":
    try:
        generate_and_validate(seed=123, out_dir=None)
    except Exception as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)