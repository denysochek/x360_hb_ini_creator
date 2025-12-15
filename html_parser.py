import argparse
import re
from urllib.parse import urlparse, unquote
from bs4 import BeautifulSoup
import sys

# Символи, які потрібно видалити з назви файлу для створення унікального заголовка секції INI
FORBIDDEN_CHARS = "!+"

def clean_title(title: str) -> str:
    """
    Очищає назву файлу, видаляючи розширення та заборонені символи,
    для використання як унікального заголовка секції INI.
    """
    # Знаходимо останню крапку, щоб видалити розширення
    last_dot_index = title.rfind('.')
    title_no_ext = title[:last_dot_index] if last_dot_index > 0 else title
    
    # Видаляємо заборонені символи
    forbidden_regex = re.compile(f'[{re.escape(FORBIDDEN_CHARS)}]')
    cleaned = forbidden_regex.sub('', title_no_ext)
    
    return cleaned.strip()

def get_dir_from_url(url: str) -> str:
    """
    Видобуває шлях до каталогу з повного URL-адреси файлу.
    Приклад: 'http://example.com/path/to/file.zip' -> 'path/to'
    """
    try:
        # Парсимо URL
        parsed_url = urlparse(url)
        # Отримуємо шлях (наприклад, /files/Redump/Microsoft%20-%20Xbox%20360/file.zip)
        path_segment = parsed_url.path
        
        # Декодуємо URL-кодування (%20, %2F тощо)
        path_decoded = unquote(path_segment)
        
        # Видаляємо початковий слеш, якщо він є
        if path_decoded.startswith('/'):
            path_decoded = path_decoded[1:]
        
        # Знаходимо останній слеш і повертаємо все, що до нього
        last_slash_index = path_decoded.rfind('/')
        if last_slash_index == -1:
            return "" 
        
        return path_decoded[:last_slash_index]
    except Exception as e:
        # У разі помилки парсингу URL
        print(f"Помилка парсингу URL: {url}. {e}", file=sys.stderr)
        return ""

def parse_html_to_database(html_content: str) -> list:
    """
    Парсить HTML-вміст, шукаючи посилання на файли та їхні розміри, 
    і повертає список об'єктів контенту.
    """
    # Використовуємо 'lxml' парсер, оскільки він швидкий та надійний
    soup = BeautifulSoup(html_content, 'lxml')
    content_list = []
    
    # Шукаємо всі рядки таблиці (<tr>), оскільки більшість списків каталогів використовує таблиці
    rows = soup.find_all('tr')

    for row in rows:
        anchor = None
        item_size = ''
        
        # 1. Знаходимо посилання на файл (<a>)
        link_elements = row.find_all('a', href=True)
        for link in link_elements:
            link_text = link.get_text(strip=True)
            # Пропускаємо посилання на батьківський каталог
            if link_text != '..' and link.get('href') != '..':
                anchor = link
                break
        
        if not anchor:
            continue
        
        # 2. Знаходимо розмір файлу
        
        # Пріоритет 1: Стиль Myrient (комірка з класом 'size')
        # Це спрацює для Myrient
        size_cell_myrient = row.find('td', class_='size')
        if size_cell_myrient:
            item_size = size_cell_myrient.get_text(strip=True)

        # Пріоритет 2: Загальний стиль (шукаємо в усіх комірках (<td>) одиниці розміру)
        # Це спрацює для Internet Archive та як fallback для Myrient
        if not item_size:
            cells = row.find_all('td')
            for cell in cells:
                text = cell.get_text(strip=True)
                
                # Підтримує: 6.5 GiB (Myrient fallback), 400M (Internet Archive), 1.5G, 100K, bytes
                size_units_regex = r'\d+(\.\d+)?\s?(K|M|G|T|P|KiB|MiB|GiB|TiB|PiB|KB|MB|GB|TB|PB|bytes)\Z'
                
                if re.search(size_units_regex, text, re.IGNORECASE):
                    item_size = text
                    break
        
        # 3. Якщо знайдено посилання та розмір, додаємо елемент
        if anchor and item_size:
            item_title = anchor.get_text(strip=True)
            data_url = anchor.get('href')
            
            unique_title = clean_title(item_title)
            path_value = get_dir_from_url(data_url)

            content_list.append({
                'unique_title': unique_title,
                'itemTitle': item_title,
                'itemVersion': '',
                'itemAuthor': '',
                'itemSize': item_size,
                'path': path_value,
                'dataurl': data_url
            })

    return content_list

def generate_ini_format(database: list) -> str:
    """
    Форматує базу даних у INI-подібний рядок.
    """
    ini_content = []
    
    for entry in database:
        ini_content.append(f"\n[{entry['unique_title']}]")
        
        ini_content.append(f"itemTitle={entry['itemTitle']}")
        
        if entry['itemVersion']:
            ini_content.append(f"itemVersion={entry['itemVersion']}")
        
        if entry['itemAuthor']:
            ini_content.append(f"itemAuthor={entry['itemAuthor']}")

        if entry['itemSize']:
            ini_content.append(f"itemSize={entry['itemSize']}")

        ini_content.append(f"path={entry['path']}")

        ini_content.append(f"dataurl={entry['dataurl']}")

    return '\n'.join(ini_content)

def main():
    """
    Основна функція для обробки аргументів командного рядка та запуску парсера.
    """
    # Налаштовуємо парсер аргументів
    parser = argparse.ArgumentParser(
        description="Парсер HTML-списків файлів для генерації бази даних у форматі INI.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'html_file', 
        type=str, 
        help="Шлях до вхідного HTML-файлу, що містить список каталогів (наприклад, input.html)."
    )
    
    args = parser.parse_args()
    
    try:
        # Зчитуємо вміст HTML-файлу
        with open(args.html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
    except FileNotFoundError:
        print(f"Помилка: Файл '{args.html_file}' не знайдено.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Помилка при читанні файлу: {e}", file=sys.stderr)
        sys.exit(1)

    # Запускаємо парсинг
    try:
        database = parse_html_to_database(html_content)
        
        if not database:
            print("Попередження: Не вдалося знайти записи про контент (посилання та розмір) у HTML-файлі. Переконайтеся, що дані містяться у структурі <tr>/<td>.", file=sys.stderr)
            sys.exit(0)

        # Генеруємо вивід у форматі INI
        ini_result = generate_ini_format(database)
        
        # Виводимо результат у стандартний вивід
        print(ini_result)
        
    except Exception as e:
        print(f"Сталася несподівана помилка під час обробки: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()