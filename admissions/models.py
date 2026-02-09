"""
Модели для управления программами и заявлениями
"""
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from applicants.models import Applicant


class Program(models.Model):
    """
    Модель образовательной программы (ОП)
    
    Хранит информацию о программах: код, название, количество мест.
    """
    
    # Код программы (PM, IVT, ITSS, IB)
    code = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        verbose_name='Код программы',
        help_text='Краткий код программы (например, PM, IVT)'
    )
    
    name = models.CharField(
        max_length=200,
        verbose_name='Название программы',
        help_text='Полное название образовательной программы'
    )
    
    seats = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Количество мест',
        help_text='Количество бюджетных мест на программе'
    )
    
    color = models.CharField(  # НОВОЕ ПОЛЕ
        max_length=50,
        default='rgb(128, 128, 128)',
        verbose_name='Цвет для графиков',
        help_text='Цвет в формате rgb(R, G, B)'
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание',
        help_text='Дополнительная информация о программе'
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    
    class Meta:
        db_table = 'programs'
        verbose_name = 'Программа'
        verbose_name_plural = 'Программы'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.name} ({self.seats} мест)"


class Application(models.Model):
    """
    Модель заявления абитуриента на программу
    
    Связывает абитуриента с программой, хранит приоритет, согласие и дату.
    Один абитуриент может иметь несколько заявлений (на разные программы).
    """
    
    # Связи с другими моделями
    applicant = models.ForeignKey(
        Applicant,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name='Абитуриент',
        help_text='Абитуриент, подавший заявление'
    )
    
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name='applications',
        verbose_name='Программа',
        help_text='Образовательная программа'
    )
    
    # Приоритет программы (1-4, где 1 - самый высокий)
    priority = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name='Приоритет',
        help_text='Приоритет программы для абитуриента (1-4)'
    )
    
    # Согласие на зачисление
    consent = models.BooleanField(
        default=False,
        db_index=True,  # Индекс для быстрой фильтрации по согласию
        verbose_name='Согласие на зачисление',
        help_text='Предоставил ли абитуриент согласие на зачисление'
    )
    
    # Дата подачи заявления (соответствует датам 01.08, 02.08, 03.08, 04.08)
    application_date = models.DateField(
        db_index=True,  # Индекс для быстрой фильтрации по датам
        verbose_name='Дата заявления',
        help_text='Дата подачи заявления (из конкурсных списков)'
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
        db_table = 'applications'
        verbose_name = 'Заявление'
        verbose_name_plural = 'Заявления'
        ordering = ['application_date', 'program', '-applicant__total_score']
        
        indexes = [
            # Для получения списков по программе и дате
            models.Index(
                fields=['program', 'application_date'],
                name='idx_prog_date'
            ),
            
            # Для фильтрации по дате и согласию
            models.Index(
                fields=['application_date', 'consent'],
                name='idx_date_consent'
            ),
            
            # Для получения заявлений абитуриента
            models.Index(
                fields=['applicant', 'application_date'],
                name='idx_appl_date'
            ),
            
            # Для эффективного удаления
            models.Index(
                fields=['application_date', 'applicant', 'program'],
                name='idx_date_appl_prog'
            ),
            
            # Для проверки существования
            models.Index(
                fields=['applicant', 'program', 'application_date'],
                name='idx_unique_check'
            ),
        ]
        
        unique_together = [
            ['applicant', 'program', 'application_date']
        ]
    
    def __str__(self):
        return (
            f"Заявление #{self.id}: "
            f"Абитуриент {self.applicant.applicant_id} → "
            f"{self.program.code} (приоритет {self.priority})"
        )
    
    def get_absolute_url(self):
        """URL для просмотра заявления"""
        from django.urls import reverse
        return reverse('applicants:application-detail', args=[str(self.id)])
 
class UploadHistory(models.Model):
    """
    Модель истории загрузок конкурсных списков
    
    Хранит информацию о каждой загрузке данных в систему.
    """
    
    upload_date = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата и время загрузки',
        help_text='Когда были загружены данные'
    )
    
    records_count = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name='Количество записей',
        help_text='Сколько записей было загружено'
    )
    
    # Дата из конкурсных списков (01.08, 02.08, и т.д.)
    competition_date = models.DateField(
        verbose_name='Дата конкурса',
        help_text='Дата из конкурсных списков (например, 01.08.2024)'
    )
    
    # Статистика по программам (JSON)
    programs_stats = models.JSONField(
        default=dict,
        blank=True,
        verbose_name='Статистика по программам',
        help_text='Количество записей по каждой программе'
    )
    
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name='Примечания',
        help_text='Дополнительная информация о загрузке'
    )
    
    # Статус загрузки
    STATUS_CHOICES = [
        ('success', 'Успешно'),
        ('partial', 'Частично'),
        ('failed', 'Ошибка'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='success',
        verbose_name='Статус',
        help_text='Статус завершения загрузки'
    )
    
    # Информация о пользователе
    uploaded_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Загрузил',
        help_text='Кто загрузил данные'
    )
    
    class Meta:
        db_table = 'upload_history'
        verbose_name = 'История загрузки'
        verbose_name_plural = 'История загрузок'
        ordering = ['-upload_date']
        indexes = [
            models.Index(fields=['-upload_date'], name='idx_upload_date'),
            models.Index(fields=['competition_date'], name='idx_comp_date'),
        ]
    
    def __str__(self):
        return (
            f"Загрузка от {self.upload_date.strftime('%d.%m.%Y %H:%M')}: "
            f"{self.records_count} записей ({self.get_status_display()})"
        )

