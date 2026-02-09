"""
Кастомные фильтры для шаблонов
"""
from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Получение элемента из словаря по ключу
    
    Использование: {{ dict|get_item:key }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)
