"""
Views для загрузки конкурсных списков и расчета проходных баллов
"""
import logging
import time
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Count
import django

from applicants.models import Applicant
from admissions.models import Program, Application, UploadHistory
from django.utils import timezone

from .forms import CSVUploadForm
from .utils.csv_parser import CSVParser, CSVParseError
from .utils.db_updater import DBUpdater
from .utils.passing_score import (
    calculate_passing_scores_for_date,
    get_passing_score_history,
    get_applicant_chances
)
from .utils.pdf_generator import PDFReportGenerator

logger = logging.getLogger(__name__)


# ============================================================================
# ЗАГРУЗКА CSV
# ============================================================================

def upload_csv(request):
    """View для загрузки CSV файлов"""
    
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            start_time = time.time()
            
            try:
                csv_files = request.FILES.getlist('csv_files')
                logger.info(f"Получено {len(csv_files)} файлов для загрузки")
                
                # ============================================
                # ПАРСИНГ ВСЕХ ФАЙЛОВ
                # ============================================
                parsed_files = []
                
                for csv_file in csv_files:
                    try:
                        parsed_data = CSVParser.parse_csv_file(
                            csv_file.file,  # file object
                            csv_file.name   # filename string
                        )

                        parsed_files.append(parsed_data)
                        
                    except CSVParseError as e:
                        messages.error(
                            request,
                            f'Ошибка парсинга файла {csv_file.name}: {str(e)}'
                        )
                        logger.error(f"Ошибка парсинга {csv_file.name}: {str(e)}")
                        return render(request, 'admissions/upload.html', {'form': form})
                    except Exception as e:
                        messages.error(
                            request,
                            f'Ошибка обработки файла {csv_file.name}: {str(e)}'
                        )
                        logger.error(f"Ошибка файла {csv_file.name}: {str(e)}", exc_info=True)
                        return render(request, 'admissions/upload.html', {'form': form})
                
                logger.info(f"Всего записей: {sum(f['records_count'] for f in parsed_files)}")
                
                # ============================================
                # ОБНОВЛЕНИЕ БД
                # ============================================
                stats = DBUpdater.update_database(parsed_files)
                
                elapsed_time = time.time() - start_time
                
                logger.info(
                    f"Загрузка завершена успешно за {elapsed_time:.2f} сек. "
                    f"Статистика: {stats}"
                )
                
                if elapsed_time > 5:
                    logger.warning(
                        f"Загрузка превысила лимит времени: {elapsed_time:.2f} сек"
                    )
                
                # ============================================
                # СОХРАНЕНИЕ ИСТОРИИ ЗАГРУЗКИ
                # ============================================
                # Определяем последнюю дату
                all_dates = [f['date'] for f in parsed_files]
                latest_date = max(all_dates)
                
                upload_history = UploadHistory.objects.create(
                    upload_date=timezone.now(),
                    competition_date=latest_date,
                    records_count=stats['total_records'],
                    programs_stats=dict(stats['programs_stats']),
                    status='success'
                )
                
                logger.info(f"Создана запись в истории загрузок: #{upload_history.id}")
                
                # ============================================
                # ОТОБРАЖЕНИЕ РЕЗУЛЬТАТОВ
                # ============================================
                context = {
                    'stats': stats,
                    'elapsed_time': elapsed_time,
                }
                
                messages.success(
                    request,
                    f'Успешно загружено {stats["total_records"]} записей '
                    f'из {stats["total_files"]} файлов за {elapsed_time:.2f} сек'
                )
                
                return render(request, 'admissions/upload_success.html', context)
                
            except Exception as e:
                logger.error(f"Непредвиденная ошибка: {str(e)}", exc_info=True)
                
                try:
                    UploadHistory.objects.create(
                        upload_date=timezone.now(),
                        records_count=0,
                        competition_date=timezone.now().date(),
                        status='failed',
                        notes=str(e)
                    )
                except:
                    pass
                
                messages.error(
                    request,
                    f'Произошла ошибка при загрузке: {str(e)}'
                )
                return render(request, 'admissions/upload.html', {'form': form})
        
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме')
    
    else:
        form = CSVUploadForm()
    
    return render(request, 'admissions/upload.html', {'form': form})


# ============================================================================
# DASHBOARD
# ============================================================================

def dashboard(request):
    """Главная страница с информацией о системе"""
    
    programs = Program.objects.annotate(
        applications_count=Count('applications')
    )
    
    context = {
        'applicants_count': Applicant.objects.count(),
        'applications_count': Application.objects.count(),
        'programs_count': Program.objects.count(),
        'programs': programs,
        'last_uploads': UploadHistory.objects.all().order_by('-upload_date')[:5],
        'django_version': django.get_version(),
    }
    
    return render(request, 'admissions/dashboard.html', context)


# ============================================================================
# ПРОХОДНЫЕ БАЛЛЫ
# ============================================================================

def passing_scores(request):
    """Отображение текущих проходных баллов"""
    
    # Получаем доступные даты
    available_dates = Application.objects.dates('application_date', 'day', order='DESC')
    
    if not available_dates:
        context = {
            'available_dates': [],
            'programs_data': {},
            'selected_date': None,
        }
        return render(request, 'admissions/passing_scores.html', context)
    
    # Определяем выбранную дату
    selected_date_str = request.GET.get('date')
    
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            if selected_date not in available_dates:
                selected_date = available_dates[0]
        except ValueError:
            selected_date = available_dates[0]
    else:
        selected_date = available_dates[0]
    
    # Рассчитываем проходные баллы
    programs_data = calculate_passing_scores_for_date(selected_date)
    
    logger.info(f"Проходные баллы на {selected_date}: {programs_data}")
    
    context = {
        'programs_data': programs_data,
        'selected_date': selected_date,
        'available_dates': available_dates,
    }
    
    return render(request, 'admissions/passing_scores.html', context)


def passing_scores_history(request):
    """История проходных баллов"""
    
    # Получаем историю
    history = get_passing_score_history()
    
    # Получаем все программы из БД
    programs = Program.objects.all().order_by('code')
    
    # Преобразуем даты в строки для JSON
    history_json = []
    for entry in history:
        history_json.append({
            'date': entry['date'].strftime('%Y-%m-%d'),
            'programs': entry['programs']
        })
    
    context = {
        'history': history,
        'history_json': json.dumps(history_json),
        'programs': programs,
    }
    
    return render(request, 'admissions/passing_scores_history.html', context)


def applicant_chances_view(request):
    """View для проверки шансов конкретного абитуриента"""
    
    if request.method == 'POST':
        applicant_id = request.POST.get('applicant_id')
        date_str = request.POST.get('date')
        
        try:
            applicant_id = int(applicant_id)
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            chances = get_applicant_chances(applicant_id, selected_date)
            
            return render(request, 'admissions/applicant_chances.html', {
                'chances': chances,
                'selected_date': selected_date,
            })
            
        except ValueError as e:
            messages.error(request, f'Ошибка: {str(e)}')
        except Exception as e:
            logger.error(f"Ошибка: {str(e)}", exc_info=True)
            messages.error(request, f'Ошибка: {str(e)}')
    
    available_dates = Application.objects.values_list(
        'application_date', 
        flat=True
    ).distinct().order_by('-application_date')
    
    return render(request, 'admissions/applicant_chances_form.html', {
        'available_dates': available_dates,
    })


# ============================================================================
# API
# ============================================================================

def passing_scores_api(request):
    """API endpoint для получения проходных баллов в JSON"""
    
    date_str = request.GET.get('date')
    
    if not date_str:
        return JsonResponse({'error': 'Параметр date обязателен'}, status=400)
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        results = calculate_passing_scores_for_date(selected_date)
        
        response_data = {
            'date': selected_date.isoformat(),
            'programs': {}
        }
        
        for program_code, data in results.items():
            response_data['programs'][program_code] = {
                'program_name': data['program_name'],
                'passing_score': data['passing_score'],
                'enrolled_count': data['enrolled_count'],
                'total_seats': data['total_seats'],
                'has_shortage': data['has_shortage'],
                'stats_by_priority': data['stats_by_priority'],
            }
        
        return JsonResponse(response_data)
        
    except ValueError:
        return JsonResponse({'error': 'Неверный формат даты'}, status=400)
    except Exception as e:
        logger.error(f"API ошибка: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# ПРОСМОТР СПИСКОВ
# ============================================================================

def applications_list(request):
    """View для просмотра списков абитуриентов с фильтрацией"""
    
    applications = Application.objects.select_related(
        'applicant', 'program'
    ).all()
    
    # Фильтрация по программе
    program_filter = request.GET.get('program')
    if program_filter:
        applications = applications.filter(program__code=program_filter)
    
    # Фильтрация по дате
    date_filter = request.GET.get('date')
    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            applications = applications.filter(application_date=date_obj)
        except ValueError:
            pass
    
    # Фильтрация по согласию
    consent_filter = request.GET.get('consent')
    if consent_filter:
        applications = applications.filter(consent=(consent_filter == '1'))
    
    # Фильтрация по приоритету
    priority_filter = request.GET.get('priority')
    if priority_filter:
        applications = applications.filter(priority=int(priority_filter))
    
    # Сортировка
    applications = applications.order_by('-applicant__total_score')
    
    # Пагинация
    paginator = Paginator(applications, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'applications': page_obj,
        'programs': Program.objects.all(),
        'available_dates': Application.objects.values_list(
            'application_date', flat=True
        ).distinct().order_by('-application_date'),
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
    }
    
    return render(request, 'admissions/applications_list.html', context)


# ============================================================================
# ОТЧЕТЫ
# ============================================================================

def reports(request):
    """View для страницы отчетов"""
    
    available_dates = Application.objects.values_list(
        'application_date', 
        flat=True
    ).distinct().order_by('-application_date')
    
    context = {
        'available_dates': available_dates,
    }
    
    return render(request, 'admissions/reports.html', context)


def generate_pdf_report(request):
    """Генерация PDF отчета"""
    
    if request.method == 'POST':
        date_str = request.POST.get('date')
        
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # Получаем данные для отчета
            programs_data = calculate_passing_scores_for_date(selected_date)
            history = get_passing_score_history()
            
            # Собираем детальную статистику по приоритетам
            for program_code, prog_data in programs_data.items():
                program = Program.objects.get(code=program_code)
                all_applications = Application.objects.filter(
                    program=program,
                    application_date=selected_date
                )
                
                # Общее количество заявлений
                prog_data['applications_total'] = all_applications.count()
                
                # Количество заявлений по приоритетам
                prog_data['priority_counts'] = {}
                for priority in [1, 2, 3, 4]:
                    prog_data['priority_counts'][priority] = all_applications.filter(
                        priority=priority
                    ).count()
                
                # Количество зачисленных по приоритетам
                enrolled_list = prog_data.get('enrolled_list', [])
                prog_data['enrolled_priority_counts'] = {}
                for priority in [1, 2, 3, 4]:
                    count = sum(1 for student in enrolled_list if student['priority'] == priority)
                    prog_data['enrolled_priority_counts'][priority] = count
            
            # Подготавливаем данные для PDF
            report_data = {
                'date': selected_date,
                'programs': programs_data,
                'history': history,
            }
            
            # Генерируем PDF
            generator = PDFReportGenerator()
            buffer = generator.generate_report(report_data)
            
            # Возвращаем PDF
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="report_{selected_date.strftime("%Y%m%d")}.pdf"'
            
            return response
            
        except Exception as e:
            logger.error(f"Ошибка генерации PDF: {str(e)}", exc_info=True)
            messages.error(request, f'Ошибка генерации отчета: {str(e)}')
            return redirect('admissions:reports')
    
    return redirect('admissions:reports')