"""
Утилиты для кэширования
"""
from django.core.cache import cache
from django.conf import settings
from admissions.models import Program


def get_programs_cache():
    """
    Получение программ с кэшированием
    """
    cache_key = 'programs_all'
    programs = cache.get(cache_key)
    
    if programs is None:
        # Кэш пуст, загружаем из БД
        programs = {
            prog.code: prog 
            for prog in Program.objects.all()
        }
        
        # Сохраняем в кэш на 1 час
        cache_ttl = getattr(settings, 'CACHE_TTL', {}).get('programs', 3600)
        cache.set(cache_key, programs, timeout=cache_ttl)
    
    return programs


def invalidate_programs_cache():
    """
    Сброс кэша программ (вызывать при изменении программ)
    """
    cache.delete('programs_all')