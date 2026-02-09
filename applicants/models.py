"""
Модели для работы с абитуриентами
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Applicant(models.Model):
    """
    Модель абитуриента
    
    Хранит базовую информацию об абитуриенте и его баллы.
    Один абитуриент может подать заявления на несколько программ.
    """
    
    # Уникальный ID из конкурсных списков (из CSV файлов)
    applicant_id = models.IntegerField(
        unique=True,
        db_index=True,
        verbose_name='ID абитуриента',
        help_text='Уникальный идентификатор из конкурсных списков'
    )
    
    # Баллы по предметам
    physics_ict_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Балл Физика/ИКТ',
        help_text='Балл по физике или ИКТ (45-100)'
    )
    
    russian_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Балл Русский язык',
        help_text='Балл по русскому языку (45-100)'
    )
    
    math_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name='Балл Математика',
        help_text='Балл по математике (45-100)'
    )
    
    achievements_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name='Балл ИД',
        help_text='Балл за индивидуальные достижения (0-10)'
    )
    
    total_score = models.IntegerField(
        db_index=True,  # Индекс для быстрой сортировки по баллам
        verbose_name='Сумма баллов',
        help_text='Общая сумма баллов'
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания записи'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления записи'
    )
    
    class Meta:
        db_table = 'applicants'
        verbose_name = 'Абитуриент'
        verbose_name_plural = 'Абитуриенты'
        ordering = ['-total_score', 'applicant_id']  # Сортировка по убыванию баллов
        indexes = [
            # Индекс для сортировки по баллам
            models.Index(fields=['-total_score', 'applicant_id'], name='idx_score_id'),
        ]
    
    def __str__(self):
        return f"Абитуриент #{self.applicant_id} ({self.total_score} баллов)"
    
    def save(self, *args, **kwargs):
        """Автоматически пересчитываем сумму баллов при сохранении"""
        self.total_score = (
            self.physics_ict_score + 
            self.russian_score + 
            self.math_score + 
            self.achievements_score
        )
        super().save(*args, **kwargs)