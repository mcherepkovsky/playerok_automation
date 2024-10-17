import json
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options


class AuthManager:
    def __init__(self, cookies_file='cookies_data.ckjson'):
        self.cookies_file = cookies_file
        self.driver = self.init_driver()

    def init_driver(self):
        """Инициализация драйвера с опциями для оптимизации."""
        options = Options()
        # Добавьте необходимые опции
        # options.add_argument("--headless")
        service = ChromeService()  # Убедитесь, что chromedriver доступен в PATH
        driver = webdriver.Chrome(service=service, options=options)
        return driver

    def login(self, url="https://playerok.com"):
        """Авторизация с загрузкой кук."""
        self.driver.get(url)
        self.load_cookies()

    def load_cookies(self):
        """Загрузка кук из файла и добавление их в браузер через Selenium."""
        try:
            with open(self.cookies_file, 'r', encoding='utf-8') as file:
                cookies = json.load(file)
        except FileNotFoundError:
            logging.error(f"Файл с куками '{self.cookies_file}' не найден.")
            return
        except json.JSONDecodeError as e:
            logging.error(f"Ошибка при чтении JSON из '{self.cookies_file}': {e}")
            return

        for cookie in cookies:
            # Удаляем параметры, которые Selenium не принимает
            for key in ['sameSite', 'storeId', 'hostOnly']:
                cookie.pop(key, None)
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                logging.error(f"Ошибка при добавлении куки: {e}")

        self.driver.refresh()

    def close(self):
        """Закрытие браузера."""
        self.driver.quit()
