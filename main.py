import multiprocessing
import json
import random
import time
from selenium.common import NoSuchElementException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import sys
from functools import wraps
import logging

from auth.auth_manager import AuthManager
from managers.delete_req_manager import DeleteReqManager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/automation.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)


def retry_on_message(max_retries=5, base_delay=10, message="попробуйте позже"):
    def decorator(func):
        @wraps(func)
        def wrapper(self, wait, *args, **kwargs):
            attempt = 1
            while attempt <= max_retries:
                try:
                    func(self, wait, *args, **kwargs)

                    # После успешного выполнения шага проверяем наличие сообщения
                    if self.check_retry_message():
                        raise Exception(message)

                    return  # Успешное выполнение, выход из функции
                except Exception as e:
                    if message in str(e).lower():
                        delay = base_delay * attempt
                        print(
                            f"Попытка {attempt} из {max_retries}: Получено сообщение '{message}'. Ожидание {delay} секунд перед повторной попыткой.")
                        time.sleep(delay)
                        attempt += 1
                    else:
                        raise  # Если ошибка не связана с сообщением, пробрасываем её дальше
            print(f"Достигнуто максимальное количество попыток ({max_retries}) для метода '{func.__name__}'. Пропуск.")

        return wrapper

    return decorator


def retry_on_exception(max_retries=5, base_delay=10, backoff_factor=2):
    """
    Декоратор для повторной попытки выполнения метода при возникновении любого исключения.

    :param max_retries: Максимальное количество повторных попыток.
    :param base_delay: Базовая задержка перед повторной попыткой в секундах.
    :param backoff_factor: Фактор увеличения задержки для экспоненциального роста.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, wait, *args, **kwargs):
            attempt = 1
            delay = base_delay
            while attempt <= max_retries:
                try:
                    func(self, wait, *args, **kwargs)
                    logging.info(f"Шаг '{func.__name__}' выполнен успешно с попытки {attempt}.")
                    return  # Успешное выполнение, выходим из функции
                except Exception as e:
                    logging.warning(f"Попытка {attempt} из {max_retries} для шага '{func.__name__}' не удалась: {e}")
                    if attempt == max_retries:
                        logging.error(
                            f"Достигнуто максимальное количество попыток ({max_retries}) для шага '{func.__name__}'. Пропуск шага.")
                        raise  # Пробрасываем исключение дальше после исчерпания попыток
                    logging.info(f"Ожидание {delay} секунд перед повторной попыткой.")
                    time.sleep(delay)
                    delay *= backoff_factor  # Увеличиваем задержку
                    attempt += 1

        return wrapper

    return decorator


class PlayerokAutomation:
    SECTION_MAPPING = {
        1: "black_russia",
        2: "arizona",
        3: "radmir",
        4: "hassle",
        5: "matreshka",
        6: "gta_5_rp",
        7: "majestic",
        8: "next_rp",
        9: "province",
        10: "rodina",
        11: "amazing"
    }

    MAX_RETRIES = 100  # Максимальное количество попыток
    BASE_DELAY = 20  # Базовая задержка в секундах для повторных попыток

    def __init__(self, section_number, card, product_data, virt_description, auth_manager):
        self.section_number = section_number
        self.section_name = self.SECTION_MAPPING.get(section_number)
        self.full_section_name = self.load_section_names()
        self.card = card
        self.product_data = product_data
        self.virt_description = virt_description
        self.auth_manager = auth_manager
        self.url = ""
        self.server_name = ""

    def load_section_names(self):
        """Загрузка полных названий секций из JSON-файла."""
        try:
            with open('data/game_names.json', 'r', encoding='utf-8') as json_file:
                return json.load(json_file)
        except FileNotFoundError:
            logging.error("Файл 'game_names.json' не найден.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при чтении JSON из 'game_names.json': {e}")
            sys.exit(1)

    def load_servers_names(self, server_name):
        """Загрузка полных названий серверов из JSON-файла."""
        try:
            with open('data/server_names.json', 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
                return data[server_name]
        except FileNotFoundError:
            logging.error("Файл 'server_names.json' не найден.")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при чтении JSON из 'server_names.json': {e}")
            sys.exit(1)

    def start_sell(self):
        """Разделяем сервера на группы по 10 и запускаем обработку для каждой группы"""
        if self.section_number in [1, 5]:
            servers = self.load_servers_names(self.full_section_name.get(str(self.section_number)))

            # Разбиваем сервера на группы по 10
            server_items = list(servers.items())
            server_groups = [server_items[i:i + 10] for i in range(0, len(server_items), 10)]

            for group_num, server_group in enumerate(server_groups, start=1):
                logging.info(f"Запуск группы {group_num} из {len(server_groups)}")
                self.auth_manager = AuthManager()  # Открываем новый браузер
                self.auth_manager.login()  # Выполняем вход

                for server_num, server_name in server_group:
                    self.server_name = server_name
                    self.url = ""
                    self.initial_actions()

                self.auth_manager.close()  # Закрываем браузер после обработки 10 серверов
                logging.info(f"Группа {group_num} завершена и браузер закрыт.")
        else:
            self.initial_actions()

    def initial_actions(self):
        """Выполнение действий на странице продажи."""
        url = "https://playerok.com/sell"
        try:
            self.auth_manager.driver.get(url)
        except Exception as e:
            logging.error(f"Не удалось открыть страницу продажи: {e}")
            self.retry_entire_sell()
            return

        # Ожидание загрузки страницы
        wait = WebDriverWait(self.auth_manager.driver, 35)

        # Выбор секции
        if not self.select_section(wait):
            logging.error(f"Раздел {self.section_number} не выбран. Завершение работы.")
            return
        else:
            logging.info(f"Раздел {self.section_number} выбран.")

        self.fill_common_fields(wait)

        logging.info(f"Карточка '{self.card['name']}' успешно обработана.")

    def check_retry_message(self):
        """Проверка наличия сообщения 'Попробуйте позже' на странице."""
        try:
            # Используем точный XPath для обнаружения сообщения
            retry_message = WebDriverWait(self.auth_manager.driver, 5).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(text(), 'Попробуйте позже')]")
                )
            )
            logging.info("Сообщение 'Попробуйте позже' обнаружено.")
            return True
        except:
            logging.info("Сообщение 'Попробуйте позже' не обнаружено.")
            return False

    def retry_entire_sell(self):
        """Механизм повторных попыток открытия страницы продажи."""
        attempt = 1
        while attempt <= self.MAX_RETRIES:
            delay = self.BASE_DELAY * (2 ** (attempt - 1))  # Экспоненциальная задержка
            logging.info(
                f"Попытка {attempt} из {self.MAX_RETRIES}: Повторный запуск процесса продажи через {delay} секунд.")
            time.sleep(delay)
            try:
                self.initial_actions()
                return  # Если успешно, выходим
            except Exception as e:
                logging.error(f"Попытка {attempt}: Ошибка при повторном запуске процесса продажи: {e}")
                attempt += 1
        logging.error(
            f"Достигнуто максимальное количество попыток ({self.MAX_RETRIES}) для карточки '{self.card['name']}'. Пропуск.")

    def select_section(self, wait):
        """Выбор раздела на странице продажи на основе номера секции."""
        try:
            if not self.section_name:
                logging.error(f"Неверный номер секции: {self.section_number}")
                return False

            full_section_name = self.full_section_name.get(str(self.section_number))
            logging.info(f"Полное название секции: {full_section_name}")
            # Найти поле ввода и ввести section_name
            search_input = wait.until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "input[name='search']"))
            )
            search_input.clear()  # Очистка поля ввода, если необходимо
            search_input.send_keys(self.section_name)  # Ввод section_name
            search_input.send_keys(Keys.RETURN)  # Отправка формы, если нужно

            # Ожидание появления и клика по элементу секции
            paragraph = wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//p[text()='{full_section_name}']"))
            )
            paragraph.click()
            return True
        except Exception as e:
            logging.error(f"Ошибка при выборе раздела: {e}")
            return False

    @retry_on_message(max_retries=5, base_delay=20, message="попробуйте позже")
    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def click_submit_button(self, wait, max_attempts=10, delay=2):
        """Нажатие кнопки отправки формы с циклической проверкой ее активности."""
        xpath = "//button[@type='submit']"
        attempt = 0
        while attempt < max_attempts:
            but_submit = self.auth_manager.driver.find_element(By.XPATH, xpath)
            if but_submit.is_enabled() and not but_submit.get_attribute("disabled"):
                self.auth_manager.driver.execute_script("arguments[0].click();", but_submit)
                logging.info("Кнопка 'Далее' нажата успешно.")
                return
            else:
                logging.info(
                    f"Кнопка 'Далее' неактивна. Попытка {attempt + 1}/{max_attempts}. Ждем {delay} секунд.")

            time.sleep(delay)
            attempt += 1

        if self.check_retry_message():
            print("Получено сообщение 'попробуйте позже'.")
            raise Exception("попробуйте позже")

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_pic(self, wait):
        """Загрузка картинок."""
        # Получение абсолютного пути к изображению
        image_filename = f"{self.card['amount']}.jpg"
        relative_image_path = os.path.join("chips", self.section_name, "pictures", image_filename)
        absolute_image_path = os.path.abspath(relative_image_path)

        # Проверка существования файла
        if not os.path.isfile(absolute_image_path):
            image_filename = f"{self.card['amount']}.png"
            relative_image_path = os.path.join("chips", self.section_name, "pictures", image_filename)
            absolute_image_path = os.path.abspath(relative_image_path)

            if not os.path.isfile(absolute_image_path):
                logging.error(f"Файл изображения не найден: {absolute_image_path}")
                raise FileNotFoundError(f"Файл изображения не найден: {absolute_image_path}")

        upload_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file' and @accept='image/*']"))
        )

        # Загрузка файла через скрытый элемент
        upload_input.send_keys(absolute_image_path)
        logging.info(f"Картинка '{image_filename}' загружена.")

        self.click_submit_button(wait)

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_pname_field(self, wait):
        """Заполнение поля названия."""
        name_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='title']"))
        )
        name = self.card["name"]
        self.auth_manager.driver.execute_script("arguments[0].value = arguments[1];", name_input, name)
        name_input.send_keys(" ")
        logging.info(f"Поле названия заполнено значением '{name}'.")

        self.click_submit_button(wait)

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_description_field(self, wait):
        """Заполнение поля Описание."""
        desc_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//textarea[@name='description']"))
        )
        self.auth_manager.driver.execute_script("arguments[0].value = arguments[1];", desc_input, self.virt_description)
        desc_input.send_keys(" ")
        logging.info("Поле описания заполнено.")

        self.click_submit_button(wait)

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_price_field(self, wait):
        """Заполнение поля цены."""
        if self.url and self.auth_manager.driver.current_url != self.url:
            self.auth_manager.driver.get(self.url)

        price_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='price']"))
        )
        price_input.clear()
        price_input.send_keys(str(self.card["rawPrice"]))
        logging.info(f"Поле цены заполнено значением '{self.card['rawPrice']}'.")

        self.click_submit_button(wait)

    @retry_on_message(max_retries=5, base_delay=20, message="попробуйте позже")
    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_product_data(self, wait):
        """Заполнение полей данных продукта."""
        if self.section_number == 1:
            radio_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//span[text()='Перевод виртов через игровой банк (без входа в аккаунт)']"))
            )
            radio_button.click()
            logging.info("Радиокнопка нажата.")

            product_data_input = wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//textarea[@name='dataFields.1ee79c37-4961-6300-0646-e1043b767644.value']"))
            )
            self.auth_manager.driver.execute_script("arguments[0].value = arguments[1];", product_data_input,
                                                    self.product_data)
            product_data_input.send_keys(" ")
        else:
            product_data_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//textarea[@name='comment']"))
            )
            self.auth_manager.driver.execute_script("arguments[0].value = arguments[1];", product_data_input,
                                                    self.product_data)
            product_data_input.send_keys(" ")

        logging.info("Поле данных продукта заполнено.")

        self.click_submit_button(wait)

        if self.check_retry_message():
            print("Получено сообщение 'попробуйте позже'.")
            raise Exception("попробуйте позже")

    def check_button(self):
        try:
            # Ищем кнопку с указанными атрибутами
            button = self.auth_manager.driver.find_element(By.XPATH,
                                                           "//button[@type='button' and text()='Выставить бесплатно на 30 дней']")
            return True  # Кнопка найдена
        except NoSuchElementException:
            return False  # Кнопка не найдена

    def transition_exh(self, wait):
        while True:
            time.sleep(10)

            if self.check_button():
                self.exhibit_card(wait)
                break  # Выходим из цикла
            else:
                self.fill_product_data(wait)
                time.sleep(5)  # Пауза перед повторной проверкой (опционально)

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def exhibit_card(self, wait):
        """Выставление карточки."""
        exhibit_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[@type='button' and text()='Выставить бесплатно на 30 дней']"))
        )
        exhibit_button.click()
        logging.info("Кнопка 'Выставить бесплатно на 30 дней' нажата.")
        # После клика декоратор проверит наличие исключения и выполнит повтор, если необходимо

    def navigate_edit_and_other_page(self):
        """Добавление /edit к текущему URL и переход на другую страницу."""
        self.url = self.auth_manager.driver.current_url
        time.sleep(2)
        try:
            current_url = self.auth_manager.driver.current_url
            if current_url.endswith('/status'):
                edit_url = current_url.replace('/status', '/edit')
            else:
                if current_url.endswith('/'):
                    edit_url = current_url + 'edit'
                else:
                    edit_url = current_url + '/edit'

            self.auth_manager.driver.get(edit_url)
            logging.info(f"Переход на страницу: {edit_url}")
        except Exception as e:
            logging.error(f"Ошибка при навигации: {e}")
            raise  # Пробрасываем исключение для обработки декоратором

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_dprice_field(self, wait):
        """Заполнение поля скидки."""
        time.sleep(2)
        price_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='price']"))
        )
        price_input.clear()
        price_input.send_keys(str(self.card["price"]))
        logging.info(f"Поле скидки заполнено значением '{self.card['price']}'.")

        self.click_submit_button(wait)
        time.sleep(5)

    @retry_on_exception(max_retries=5, base_delay=20, backoff_factor=2)
    def fill_common_fields(self, wait):
        """Заполнение общих полей формы."""
        but_virt = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Вирты']"))
        )
        but_virt.click()
        logging.info("Кнопка 'Вирты' нажата.")

        if self.section_number in [1, 5]:
            self.choose_server_click(wait, self.server_name)
            self.input_virt_count(wait, "amount")
            self.click_submit_button(wait)
        elif self.section_number == 2:
            self.choose_server_click(wait, "Любой")
            self.input_virt_count(wait, "amount")
            self.click_submit_button(wait)
        elif self.section_number == 10:
            self.input_virt_count(wait, "chips")
            self.click_submit_button(wait)

        self.fill_pic(wait)
        self.fill_pname_field(wait)
        self.fill_description_field(wait)
        self.fill_price_field(wait)
        self.fill_product_data(wait)
        self.transition_exh(wait)

        self.navigate_edit_and_other_page()
        self.fill_dprice_field(wait)

    def choose_server_click(self, wait, server):
        """Выбор сервера и клик по кнопке 'Далее'."""
        choose_server = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH,
                 f"//div[@class='MuiBox-root mui-style-1p30snl' and @aria-checked='false' and text()='{server}']"))
        )

        choose_server.click()
        logging.info("Кнопка 'Выбрать сервер' нажата.")

    def input_virt_count(self, wait, type):
        """Ввод количества виртов."""
        amount_input = wait.until(
            EC.presence_of_element_located((By.XPATH, f"//input[@name='{type}']"))
        )

        amount_input.clear()
        amount_input.send_keys(str(self.card['amount']))
        logging.info(f"Поле Количества виртов заполнено значением '{self.card['amount']}'.")


def run_bot_for_card(section_number, card, product_data, virt_description, delay=0):
    """Функция для запуска бота с возможной задержкой и обработкой ошибок"""
    if delay > 0:
        logging.info(f"Задержка перед запуском карточки '{card['name']}' на {delay:.2f} секунд.")
        time.sleep(delay)  # Задержка перед началом

    auth_manager = AuthManager()
    bot = PlayerokAutomation(section_number, card, product_data, virt_description, auth_manager)
    try:
        auth_manager.login()
        bot.start_sell()
    except Exception as e:
        logging.error(f"Общая ошибка при обработке карточки '{card['name']}': {e}")
    finally:
        auth_manager.close()


def create_cards():
    # Отображение меню выбора раздела
    print("Выберите раздел для обработки:")
    for num, name in PlayerokAutomation.SECTION_MAPPING.items():
        print(f"{num}. {name}")

    try:
        section_number = int(input("Введите номер раздела: "))
        if section_number not in PlayerokAutomation.SECTION_MAPPING:
            print("Неверный номер раздела.")
            sys.exit(1)
    except ValueError:
        print("Пожалуйста, введите корректный номер раздела.")
        sys.exit(1)

    # Путь к файлу с карточками выбранного раздела
    section_name = PlayerokAutomation.SECTION_MAPPING[section_number]
    card_file = f'chips/{section_name}/presets.json'
    desc_file = 'data/descriptions.json'

    # Загрузка описания из JSON-файла
    try:
        with open(desc_file, 'r', encoding='utf-8') as f:
            descriptions_file = json.load(f)

        # Извлекаем описание для выбранного сервера
        virt_description = descriptions_file["descriptions"].get(section_name, {}).get("virt_description", "")
        product_data = descriptions_file["product_data"]["text"]

    except FileNotFoundError:
        logging.error(f"Файл {desc_file} не найден.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {desc_file}: {e}")
        sys.exit(1)

    # Загрузка карточек из JSON-файла
    try:
        with open(card_file, 'r', encoding='utf-8') as f:
            cards = json.load(f)
    except FileNotFoundError:
        logging.error(f"Файл {card_file} не найден.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Ошибка при чтении JSON из файла {card_file}: {e}")
        sys.exit(1)

    if not cards:
        logging.error(f"Файл {card_file} пуст.")
        sys.exit(1)

    # Настройка multiprocessing.Pool
    max_processes = 3  # Максимальное количество параллельных процессов

    with multiprocessing.Pool(processes=max_processes) as pool:
        for index, card in enumerate(cards):
            # Добавление случайной задержки (например, до 10 секунд) для каждого задания
            delay = random.uniform(1, 15)
            pool.apply_async(run_bot_for_card, args=(section_number, card, product_data, virt_description, delay))

        pool.close()
        pool.join()

    logging.info("Все процессы завершены.")


def delete_cards():
    print("Ожидайте, идет загрузка доступных для удаления карточек.")

    delete_mng = DeleteReqManager()
    exist_free_cards = delete_mng.fetch_existing_cards()

    if exist_free_cards:
        logging.info(f"Найденные бесплатные карточки: {exist_free_cards}")

        print("Выберите раздел для удаления относящихся к нему бесплатных карточек:")
        print("0. Удалить всё")

        unique_cards = list(set(exist_free_cards.values()))
        for i, value in enumerate(unique_cards, 1):
            print(f"{i}. {value}")

        try:
            section_number = int(input("Введите номер раздела: "))
            if section_number not in range(0, len(unique_cards) + 1):
                print("Неверный номер раздела.")
                sys.exit(1)
        except ValueError:
            print("Пожалуйста, введите корректный номер раздела.")
            sys.exit(1)

        if section_number == 0:
            matching_keys = list(exist_free_cards.keys())
        else:
            selected_value = unique_cards[section_number - 1]
            # Находим все ключи, соответствующие выбранному значению
            matching_keys = [key for key, value in exist_free_cards.items() if value == selected_value]

        # отправка ссылок
        results_deleting = delete_mng.delete_cards_parallel(matching_keys)
        for result in results_deleting:
            print(result)
    else:
        print("Нет доступных для удаления карточек.")


def main():
    print("Выберите действие:\n1. Создание карточек\n2. Удаление карточек")

    try:
        action = int(input("Введите номер действия: "))
        if action not in [1, 2]:
            print("Неверный номер раздела.")
            sys.exit(1)
    except ValueError:
        print("Пожалуйста, введите корректный номер раздела.")
        sys.exit(1)

    if action == 1:
        create_cards()
    elif action == 2:
        delete_cards()

    print("Программа завершена.")


if __name__ == "__main__":
    main()
