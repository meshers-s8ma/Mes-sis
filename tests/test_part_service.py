# tests/test_part_service.py

import pytest
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage

from app import db
from app.services import part_service
from app.models.models import Part, RouteTemplate, Stage, User


@pytest.fixture
def mock_csv_file():
    """
    Создает фикстуру с "моковым" CSV-файлом в памяти,
    имитирующим структуру файла "Наборка-№3.csv".
    """
    csv_content = """
"","","","","","",""
"","Наборка №3","","","","",""
"№","Обозначение","Наименование","Кол-во","Размер","Операции","Прим."
"","АСЦБ-000475","Палец","1","","Ток,Фр","Ст3"
"","АСЦБ-000459","Болт осевой","5","S24х530","Св,HRC","30ХГСА"
"","АСЦБ-000461","Ограничитель","4","ф12х140","Ток","Ст45"
"""
    # Создаем объект FileStorage, который ожидает Flask
    file_storage = FileStorage(
        stream=io.BytesIO(csv_content.encode('utf-8')),
        filename="test_import.csv",
        content_type="text/csv"
    )
    return file_storage


class TestPartService:
    """Тесты для сервиса, отвечающего за бизнес-логику деталей."""

    def test_import_from_hierarchical_csv(self, database, mock_csv_file):
        """
        Тест: Проверяет импорт из CSV-файла со сложной иерархической структурой.
        """
        # 1. Подготовка
        # Получаем пользователя-админа из фикстуры database
        admin_user = User.query.filter_by(username='admin').first()
        # "Моковый" объект config, необходимый для функции
        mock_config = {'UPLOAD_FOLDER': '/tmp'}

        # 2. Вызываем тестируемую функцию
        added_count, skipped_count = part_service.import_parts_from_excel(
            mock_csv_file, admin_user, mock_config
        )

        # 3. Проверяем результат
        # 3.1. Проверяем счетчики
        assert added_count == 3
        assert skipped_count == 0

        # 3.2. Проверяем созданные детали
        part1 = db.session.get(Part, "АСЦБ-000475")
        assert part1 is not None
        assert part1.product_designation == "Наборка №3"
        assert part1.name == "Палец"
        assert part1.quantity_total == 1
        assert part1.material == "Ст3"
        
        part2 = db.session.get(Part, "АСЦБ-000459")
        assert part2 is not None
        assert part2.product_designation == "Наборка №3"
        assert part2.name == "Болт осевой"
        assert part2.size == "S24х530"
        assert part2.material == "30ХГСА"

        part3 = db.session.get(Part, "АСЦБ-000461")
        assert part3 is not None
        assert part3.quantity_total == 4
        assert part3.material == "Ст45"

        # 3.3. Проверяем автоматически созданные маршруты
        route1 = RouteTemplate.query.filter_by(name="Ток -> Фр").first()
        assert route1 is not None
        assert len(route1.stages) == 2
        assert route1.stages[0].stage.name == "Ток"
        assert route1.stages[1].stage.name == "Фр"

        route2 = RouteTemplate.query.filter_by(name="Св -> HRC").first()
        assert route2 is not None
        assert len(route2.stages) == 2

        route3 = RouteTemplate.query.filter_by(name="Ток").first()
        assert route3 is not None
        assert len(route3.stages) == 1

        # 3.4. Проверяем связь деталей с маршрутами
        assert part1.route_template_id == route1.id
        assert part2.route_template_id == route2.id
        assert part3.route_template_id == route3.id

        # 3.5. Проверяем, что этапы были добавлены в справочник
        assert Stage.query.filter_by(name="Ток").first() is not None
        assert Stage.query.filter_by(name="Фр").first() is not None
        assert Stage.query.filter_by(name="Св").first() is not None
        assert Stage.query.filter_by(name="HRC").first() is not None
    
    @patch('app.services.part_service.socketio.emit')
    def test_websocket_notification_on_create(self, mock_emit, database):
        """
        Тест: Проверяет, что при создании детали отправляется WebSocket-уведомление.
        """
        # 1. Подготовка
        admin_user = User.query.filter_by(username='admin').first()
        # "Моковый" объект формы с данными
        mock_form = MagicMock()
        mock_form.part_id.data = "NEW-001"
        mock_form.product.data = "Новое Изделие"
        mock_form.name.data = "Новая Деталь"
        mock_form.material.data = "Титан"
        mock_form.route_template.data = RouteTemplate.query.first().id
        mock_form.quantity_total.data = 10
        mock_form.drawing.data = None

        # 2. Вызываем функцию создания детали
        part_service.create_single_part(mock_form, admin_user, {})
        
        # 3. Проверяем, что emit был вызван с правильными аргументами
        mock_emit.assert_called_once_with('notification', {
            'event': 'part_created',
            'message': f"Пользователь {admin_user.username} создал деталь: NEW-001",
            'part_id': 'NEW-001'
        })