import os
import re
import sys
from urllib.parse import urlparse

# Для роботи скрипта вам потрібно встановити бібліотеку BeautifulSoup:
# pip install beautifulsoup4

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Помилка: Бібліотека 'beautifulsoup4' не знайдена.")
    print("Будь ласка, встановіть її за допомогою команди: pip install beautifulsoup4")
    exit()

# Назва вхідного HTML-файлу, тепер це змінна, яку ми отримаємо з аргументів.
# HTML_FILE = "Content Listing _ Myrient.html" # Видалено жорстке кодування
# Назва вихідного файлу в INI-подібному форматі.
OUTPUT_FILE = "submenu_database.ini"
# Символи, які заборонено використовувати у [Unique Title]
FORBIDDEN_CHARS = "!+"

def clean_title(title: str) -> str:
    """Очищає назву файлу для використання як унікальний заголовок INI-секції."""
    # 1. Видаляємо розширення файлу (наприклад, .zip, .7z)
    title_no_ext = os.path.splitext(title)[0]
    # 2. Видаляємо заборонені символи
    cleaned = re.sub(f'[{re.escape(FORBIDDEN_CHARS)}]', '', title_no_ext)
    # 3. Видаляємо зайві пробіли та очищаємо
    return cleaned.strip()

def get_dir_from_url(url: str) -> str:
    """Витягує шлях до каталогу з URL-адреси завантаження."""
    parsed_url = urlparse(url)
    # Отримуємо сегмент шляху (наприклад, /files/Redump/Microsoft%20-%20Xbox%20360/filename.zip)
    path_segment = parsed_url.path
    # Декодуємо URL-кодування
    path_decoded = path_segment.replace('%20', ' ')

    # Знаходимо останній слеш і повертаємо все до нього (це буде каталог)
    dir_path = os.path.dirname(path_decoded.lstrip('/'))
    return dir_path

def parse_html_to_database(html_content: str) -> list:
    """Парсить HTML-контент і повертає список словників з даними контенту."""
    soup = BeautifulSoup(html_content, 'html.parser')
    content_list = []

    # Шукаємо всі рядки таблиці (<tr>).
    # У типових списках каталогів кожен рядок відповідає файлу або папці.

    # Припускаємо, що список знаходиться в таблиці, а файли - в <tr>
    # Спробуємо знайти всі <tr>, які мають <td> з класом 'link'
    for row in soup.find_all('tr'):
        link_cell = row.find('td', class_='link')
        size_cell = row.find('td', class_='size')

        # Перевіряємо, чи є в рядку посилання на файл і його розмір
        if link_cell and size_cell:
            anchor = link_cell.find('a')

            if anchor and anchor.get('href') and anchor.text.strip():
                item_title = anchor.text.strip()
                data_url = anchor.get('href')
                item_size = size_cell.text.strip()

                # Припускаємо, що [Unique Title] має бути чистим
                unique_title = clean_title(item_title)

                # Припускаємо, що path - це каталог, який містить файл
                path_value = get_dir_from_url(data_url)

                # Збираємо дані
                content_entry = {
                    "unique_title": unique_title,
                    "itemTitle": item_title,
                    "itemVersion": "",  # Неможливо витягти з цього HTML
                    "itemAuthor": "",   # Неможливо витягти з цього HTML
                    "itemSize": item_size,
                    "path": path_value,
                    "itemDescription": "", # Неможливо витягти з цього HTML
                    "dataurl": data_url
                }
                content_list.append(content_entry)

    return content_list

def generate_ini_format(database: list) -> str:
    """Форматує базу даних у INI-подібний рядок."""
    ini_content = []

    for entry in database:
        # [Unique Title]
        ini_content.append(f"\n[{entry['unique_title']}]")

        # itemTitle
        ini_content.append(f"itemTitle={entry['itemTitle']}")

        # itemVersion (опціонально)
        if entry['itemVersion']:
            ini_content.append(f"itemVersion={entry['itemVersion']}")

        # itemAuthor (опціонально)
        if entry['itemAuthor']:
            ini_content.append(f"itemAuthor={entry['itemAuthor']}")

        # itemSize (опціонально)
        if entry['itemSize']:
            ini_content.append(f"itemSize={entry['itemSize']}")

        # path
        ini_content.append(f"path={entry['path']}")

        # itemDescription (опціонально)
        if entry['itemDescription']:
            ini_content.append(f"itemDescription={entry['itemDescription']}")

        # dataurl
        ini_content.append(f"dataurl={entry['dataurl']}")

    return "\n".join(ini_content)

def main():
    # Перевіряємо, чи був переданий аргумент командного рядка
    if len(sys.argv) < 2:
        print("Використання: python html_parser.py <назва_html_файлу>")
        print("Приклад: python html_parser.py my_content_list.html")
        return

    # Отримуємо назву вхідного файлу з першого аргументу командного рядка
    HTML_FILE = sys.argv[1]

    print(f"Початок обробки файлу: {HTML_FILE}")

    # 1. Завантаження HTML-файлу
    try:
        with open(HTML_FILE, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except FileNotFoundError:
        print(f"Помилка: Файл '{HTML_FILE}' не знайдено.")
        print("Переконайтеся, що файл знаходиться в тому ж каталозі, що й скрипт.")
        return
    except Exception as e:
        print(f"Помилка під час читання файлу: {e}")
        return

    # 2. Парсинг HTML
    database = parse_html_to_database(html_content)

    if not database:
        print("Не вдалося знайти записи про контент (посилання та розмір) у HTML-файлі.")
        print("Можливо, структура таблиці відрізняється від очікуваної.")
        return

    print(f"Успішно знайдено {len(database)} записів контенту.")

    # 3. Генерація INI-подібного формату
    ini_output = generate_ini_format(database)

    # 4. Збереження результату
    try:
        # Використовуємо постійну назву вихідного файлу
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(ini_output)
        print(f"База даних успішно збережена у файлі: {OUTPUT_FILE}")
        print("Вам може знадобитися вручну переглянути та додати/відредагувати поля 'itemVersion', 'itemAuthor' та 'itemDescription'.")
    except Exception as e:
        print(f"Помилка під час збереження файлу: {e}")

if __name__ == "__main__":
    main()
