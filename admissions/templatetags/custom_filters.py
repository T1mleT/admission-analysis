"""
Кастомные фильтры для Django шаблонов
"""
from django import template
import json

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Получить элемент из словаря по ключу
    
    Использование: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def split(value, arg):
    """
    Разбить строку по разделителю
    
    Использование: {{ "a,b,c"|split:"," }}
    """
    return value.split(arg)


@register.filter
def to_json(value):
    """
    Преобразовать Python объект в JSON
    
    Использование: {{ my_dict|to_json }}
    """
    return json.dumps(value)

@register.filter
def format_time(value):
    """Форматирует время в секундах с одним знаком после запятой"""
    try:
        return f"{float(value):.1f}"
    except (ValueError, TypeError):
        return value