from django.shortcuts import render
from django.http import HttpResponse

def index(request):
    """Главная страница системы"""
    return HttpResponse("<h1>Система анализа поступления</h1><p>Проект успешно инициализирован!</p>")