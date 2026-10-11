import pytest
from django.template.loader import render_to_string


@pytest.mark.django_db
def test_404_uses_themed_template(client):
    response = client.get("/no-such-page/")
    assert response.status_code == 404
    assert "Сторінку не знайдено" in response.content.decode()


def test_500_template_renders_without_context():
    # Django renders 500.html with an empty context and no request.
    html = render_to_string("500.html")
    assert "Збій бортових систем" in html
    assert "Traceback" not in html
