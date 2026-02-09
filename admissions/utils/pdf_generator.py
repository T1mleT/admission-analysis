"""
Генератор PDF отчетов для системы анализа поступления
"""
import os
from datetime import date, datetime
from io import BytesIO
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, 
    Spacer, PageBreak, Image, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.legends import Legend

from django.conf import settings


class PDFReportGenerator:
    """
    Генератор PDF отчетов о проходных баллах
    """
    
    def __init__(self):
        """Инициализация генератора"""
        self._register_fonts()
        self.styles = self._create_styles()
        self.colors = {
            'PM': colors.HexColor('#FF6384'),
            'IVT': colors.HexColor('#36A2EB'),
            'ITSS': colors.HexColor('#FFCE56'),
            'IB': colors.HexColor('#4BC0C0'),
        }
    
    def _register_fonts(self):
        """Регистрация шрифтов для поддержки русского языка"""
        try:
            # Пытаемся использовать системные шрифты
            font_path = os.path.join(settings.BASE_DIR, 'admissions', 'static', 'fonts')
            
            if os.path.exists(os.path.join(font_path, 'DejaVuSans.ttf')):
                pdfmetrics.registerFont(TTFont('DejaVu', os.path.join(font_path, 'DejaVuSans.ttf')))
                pdfmetrics.registerFont(TTFont('DejaVu-Bold', os.path.join(font_path, 'DejaVuSans-Bold.ttf')))
            else:
                # Используем стандартные шрифты
                print("Warning: Custom fonts not found, using default fonts")
        except Exception as e:
            print(f"Font registration error: {e}")
    
    def _create_styles(self):
        """Создание стилей для документа"""
        styles = getSampleStyleSheet()
        
        # Заголовок
        styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=styles['Heading1'],
            fontName='DejaVu-Bold',
            fontSize=24,
            textColor=colors.HexColor('#0d6efd'),
            spaceAfter=30,
            alignment=TA_CENTER,
        ))
        
        # Подзаголовок
        styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=styles['Heading2'],
            fontName='DejaVu-Bold',
            fontSize=16,
            textColor=colors.HexColor('#212529'),
            spaceAfter=12,
            spaceBefore=20,
        ))
        
        # Обычный текст
        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['Normal'],
            fontName='DejaVu',
            fontSize=10,
            textColor=colors.HexColor('#495057'),
        ))
        
        # Дата
        styles.add(ParagraphStyle(
            name='DateStyle',
            parent=styles['Normal'],
            fontName='DejaVu',
            fontSize=10,
            textColor=colors.HexColor('#6c757d'),
            alignment=TA_RIGHT,
        ))
        
        return styles
    
    def generate_report(
        self, 
        report_data: Dict,
        output_path: str = None
    ) -> BytesIO:
        """
        Генерация PDF отчета
        """
        # Создаем буфер
        buffer = BytesIO()
        
        # Создаем документ
        if output_path:
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )
        else:
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm,
            )
        
        # Собираем элементы
        story = []
        
        # 1. Заголовок
        story.extend(self._create_header(report_data))
        
        # 2. Проходные баллы
        story.append(Spacer(1, 0.5*cm))
        story.extend(self._create_passing_scores_table(report_data))
        
        # 3. Графики динамики
        story.append(PageBreak())
        story.extend(self._create_dynamics_charts(report_data))
        
        # 4. Списки зачисленных
        story.append(PageBreak())
        story.extend(self._create_enrolled_lists(report_data))
        
        # 5. Статистика по программам
        story.append(PageBreak())
        story.extend(self._create_statistics_table(report_data))
        
        # Генерируем PDF
        doc.build(story)
        
        if not output_path:
            buffer.seek(0)
            return buffer
        
        return None
    
    def _create_header(self, data: Dict) -> List:
        """Создание заголовка отчета"""
        elements = []
        
        # Заголовок
        title = Paragraph(
            "Отчет о проходных баллах",
            self.styles['CustomTitle']
        )
        elements.append(title)
        
        # Дата и время
        report_date = data.get('date', date.today())
        generation_time = datetime.now().strftime('%d.%m.%Y %H:%M')
        
        date_text = Paragraph(
            f"Дата конкурса: <b>{report_date.strftime('%d.%m.%Y')}</b><br/>"
            f"Сформирован: {generation_time}",
            self.styles['DateStyle']
        )
        elements.append(date_text)
        
        elements.append(Spacer(1, 0.5*cm))
        
        # Разделительная линия
        elements.append(self._create_line())
        
        return elements
    
    def _create_passing_scores_table(self, data: Dict) -> List:
        """Создание таблицы проходных баллов"""
        elements = []

        # Заголовок секции
        heading = Paragraph(
            "1. Проходные баллы на образовательные программы",
            self.styles['CustomHeading']
        )
        elements.append(heading)

        # Стиль для текста в ячейках
        cell_style = ParagraphStyle(
            name='CellStyle',
            parent=self.styles['CustomBody'],
            fontSize=9,
            leading=11,  # Межстрочный интервал
            alignment=TA_CENTER,
        )

        cell_style_left = ParagraphStyle(
            name='CellStyleLeft',
            parent=self.styles['CustomBody'],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
        )

        # Данные для таблицы - ЗАГОЛОВКИ
        table_data = [
            [
                Paragraph('<b>Программа</b>', cell_style),
                Paragraph('<b>Название</b>', cell_style),
                Paragraph('<b>Мест</b>', cell_style),
                Paragraph('<b>Проходной балл</b>', cell_style),
                Paragraph('<b>Зачислено</b>', cell_style),
                Paragraph('<b>Статус</b>', cell_style),
            ]
        ]

        programs = data.get('programs', {})

        # Данные программ
        for code in ['PM', 'IVT', 'ITSS', 'IB']:
            prog_data = programs.get(code, {})

            # Используем Paragraph для переноса текста
            table_data.append([
                Paragraph(f'<b>{code}</b>', cell_style),
                Paragraph(prog_data.get('program_name', ''), cell_style_left),  # Выравнивание по левому краю
                Paragraph(str(prog_data.get('total_seats', 0)), cell_style),
                Paragraph(str(prog_data.get('passing_score', 'НЕДОБОР')), cell_style),
                Paragraph(str(prog_data.get('enrolled_count', 0)), cell_style),
                Paragraph(
                    'Набор завершен' if not prog_data.get('has_shortage', True) else 'Недобор',
                    cell_style
                ),
            ])

        # Создаем таблицу с правильными пропорциями
        table = Table(
            table_data, 
            colWidths=[2*cm, 6*cm, 1.8*cm, 2.5*cm, 2*cm, 2.7*cm]
        )

        # Стили таблицы
        table.setStyle(TableStyle([
            # Заголовок
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),  # Вертикальное выравнивание
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),

            # Данные
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Название по левому краю
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))

        elements.append(table)

        return elements
    
    def _create_dynamics_charts(self, data: Dict) -> List:
        """Создание графиков динамики проходных баллов"""
        elements = []
        
        # Заголовок секции
        heading = Paragraph(
            "2. Динамика проходных баллов",
            self.styles['CustomHeading']
        )
        elements.append(heading)
        
        # Получаем данные истории
        history = data.get('history', [])
        
        if not history:
            elements.append(Paragraph(
                "Недостаточно данных для построения графиков",
                self.styles['CustomBody']
            ))
            return elements
        
        # Создаем график для каждой программы
        for program_code in ['PM', 'IVT', 'ITSS', 'IB']:
            chart_elements = self._create_program_chart(program_code, history)
            elements.extend(chart_elements)
            elements.append(Spacer(1, 0.5*cm))
        
        return elements
    
    def _create_program_chart(self, program_code: str, history: List) -> List:
        """Создание графика для одной программы"""
        elements = []
        
        # Подготовка данных
        dates = []
        scores = []
        
        for entry in history:
            dates.append(entry['date'].strftime('%d.%m'))
            prog_data = entry['programs'].get(program_code, {})
            score = prog_data.get('passing_score')
            
            # Пропускаем НЕДОБОР
            if score == "НЕДОБОР" or score is None:
                scores.append(None)
            else:
                scores.append(score)
        
        # Фильтруем None значения
        filtered_data = [(d, s) for d, s in zip(dates, scores) if s is not None]
        
        if not filtered_data:
            return elements
        
        dates, scores = zip(*filtered_data)
        
        # Создаем график
        drawing = Drawing(400, 200)
        
        chart = HorizontalLineChart()
        chart.x = 50
        chart.y = 50
        chart.height = 120
        chart.width = 300
        chart.data = [scores]
        chart.categoryAxis.categoryNames = dates
        chart.categoryAxis.labels.fontSize = 8
        chart.categoryAxis.labels.fontName = 'DejaVu'
        chart.valueAxis.valueMin = min(scores) - 5
        chart.valueAxis.valueMax = max(scores) + 5
        chart.valueAxis.labels.fontName = 'DejaVu'
        chart.lines[0].strokeColor = self.colors.get(program_code, colors.blue)
        chart.lines[0].strokeWidth = 2
        
        # Заголовок графика
        prog_names = {
            'PM': 'Прикладная математика',
            'IVT': 'Информатика и ВТ',
            'ITSS': 'Инфокоммуникационные технологии',
            'IB': 'Информационная безопасность'
        }
        
        from reportlab.graphics.shapes import String
        title = String(200, 180, prog_names.get(program_code, program_code))
        title.fontSize = 12
        title.fontName = 'DejaVu-Bold'
        title.textAnchor = 'middle'
        
        drawing.add(title)
        drawing.add(chart)
        
        elements.append(drawing)
        
        return elements
    
    def _create_enrolled_lists(self, data: Dict) -> List:
        """Создание списков зачисленных"""
        elements = []

        # Заголовок секции
        heading = Paragraph(
            "3. Списки зачисленных абитуриентов",
            self.styles['CustomHeading']
        )
        elements.append(heading)

        # Стиль для текста в ячейках
        cell_style = ParagraphStyle(
            name='EnrolledCellStyle',
            parent=self.styles['CustomBody'],
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        )

        programs = data.get('programs', {})

        prog_names = {
            'PM': 'Прикладная математика',
            'IVT': 'Информатика и вычислительная техника',
            'ITSS': 'Инфокоммуникационные технологии и системы связи',
            'IB': 'Информационная безопасность'
        }

        for code in ['PM', 'IVT', 'ITSS', 'IB']:
            prog_data = programs.get(code, {})
            enrolled = prog_data.get('enrolled_list', [])

            if not enrolled:
                continue
            
            # Подзаголовок программы с переносом
            prog_heading = Paragraph(
                f"<b>{code}</b> - {prog_names.get(code, prog_data.get('program_name', ''))}",
                ParagraphStyle(
                    name='ProgHeading',
                    parent=self.styles['CustomBody'],
                    fontSize=11,
                    fontName='DejaVu-Bold',
                    spaceAfter=6,
                )
            )
            elements.append(Spacer(1, 0.3*cm))
            elements.append(prog_heading)

            # Таблица зачисленных - ЗАГОЛОВКИ
            table_data = [
                [
                    Paragraph('<b>№</b>', cell_style),
                    Paragraph('<b>ID абитуриента</b>', cell_style),
                    Paragraph('<b>Сумма баллов</b>', cell_style),
                    Paragraph('<b>Приоритет</b>', cell_style),
                ]
            ]

            for idx, student in enumerate(enrolled[:20], 1):  # Первые 20
                table_data.append([
                    Paragraph(str(idx), cell_style),
                    Paragraph(str(student['applicant_id']), cell_style),
                    Paragraph(str(student['total_score']), cell_style),
                    Paragraph(str(student['priority']), cell_style),
                ])

            if len(enrolled) > 20:
                table_data.append([
                    Paragraph('...', cell_style),
                    Paragraph(f'и еще {len(enrolled) - 20} чел.', cell_style),
                    Paragraph('', cell_style),
                    Paragraph('', cell_style),
                ])

            table = Table(table_data, colWidths=[1.5*cm, 4*cm, 3*cm, 2.5*cm])

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))

            elements.append(table)
            elements.append(Spacer(1, 0.5*cm))

        return elements
    
    def _create_statistics_table(self, data: Dict) -> List:
        """Создание таблицы статистики по программам"""
        elements = []

        # Заголовок секции
        heading = Paragraph(
            "4. Статистика по образовательным программам",
            self.styles['CustomHeading']
        )
        elements.append(heading)

        # Стиль для текста в ячейках
        cell_style = ParagraphStyle(
            name='StatsCellStyle',
            parent=self.styles['CustomBody'],
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        )

        cell_style_left = ParagraphStyle(
            name='StatsCellStyleLeft',
            parent=self.styles['CustomBody'],
            fontSize=9,
            leading=11,
            alignment=TA_LEFT,
        )

        # Данные для таблицы - ЗАГОЛОВКИ
        table_data = [
            [
                Paragraph('<b>Показатель</b>', cell_style_left),
                Paragraph('<b>ПМ</b>', cell_style),
                Paragraph('<b>ИВТ</b>', cell_style),
                Paragraph('<b>ИТСС</b>', cell_style),
                Paragraph('<b>ИБ</b>', cell_style),
            ]
        ]

        programs = data.get('programs', {})

        # Строки таблицы в соответствии с ТЗ
        rows = [
            ('Общее кол-во заявлений', 'applications_total'),
            ('Количество мест на ОП', 'total_seats'),
            ('Кол-во заявлений 1-го приоритета', 'priority_1'),
            ('Кол-во заявлений 2-го приоритета', 'priority_2'),
            ('Кол-во заявлений 3-го приоритета', 'priority_3'),
            ('Кол-во заявлений 4-го приоритета', 'priority_4'),
            ('Кол-во зачисленных 1-го приоритета', 'enrolled_priority_1'),
            ('Кол-во зачисленных 2-го приоритета', 'enrolled_priority_2'),
            ('Кол-во зачисленных 3-го приоритета', 'enrolled_priority_3'),
            ('Кол-во зачисленных 4-го приоритета', 'enrolled_priority_4'),
        ]

        for row_name, key in rows:
            row = [Paragraph(row_name, cell_style_left)]

            for code in ['PM', 'IVT', 'ITSS', 'IB']:
                prog_data = programs.get(code, {})

                if key == 'total_seats':
                    # Количество мест
                    value = prog_data.get(key, 0)
                elif key == 'applications_total':
                    # Общее количество заявлений
                    value = prog_data.get(key, 0)
                elif key.startswith('priority_'):
                    # Количество заявлений по приоритету
                    priority = int(key.split('_')[1])
                    priority_counts = prog_data.get('priority_counts', {})
                    value = priority_counts.get(priority, 0)
                elif key.startswith('enrolled_priority_'):
                    # Количество зачисленных по приоритету
                    priority = int(key.split('_')[2])
                    enrolled_counts = prog_data.get('enrolled_priority_counts', {})
                    value = enrolled_counts.get(priority, 0)
                else:
                    value = 0

                row.append(Paragraph(str(value), cell_style))

            table_data.append(row)

        # Создаем таблицу
        table = Table(table_data, colWidths=[7*cm, 2.2*cm, 2.2*cm, 2.2*cm, 2.2*cm])

        table.setStyle(TableStyle([
            # Заголовок
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'DejaVu'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),

            # Выделяем строку с количеством мест
            ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e7f3ff')),
            ('FONTNAME', (0, 1), (-1, 1), 'DejaVu-Bold'),

            # Чередующиеся цвета строк (начиная со 2-й строки)
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),

            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))

        elements.append(table)

        return elements
    
    def _create_line(self):
        """Создание горизонтальной линии"""
        from reportlab.platypus import HRFlowable
        return HRFlowable(
            width="100%",
            thickness=1,
            color=colors.HexColor('#dee2e6'),
            spaceBefore=5,
            spaceAfter=5,
        )