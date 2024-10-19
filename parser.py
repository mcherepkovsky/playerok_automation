import logging
import multiprocessing
import random
import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from auth_manager import AuthManager


class ProductParser:
    def __init__(self):
        self.auth_manager = AuthManager()
        self.product_links = list()

    def run_parser(self):
        """Метод автоматизации."""
        logging.basicConfig(level=logging.INFO)

        try:
            self.auth_manager.login()

            # Переход к нужной секции (замените на реальный URL секции)
            section_url = "https://playerok.com/profile/"  # Замените на реальный URL
            self.navigate_to_section(section_url)

            # Прокрутка страницы до конца для подгрузки всех продуктов (если необходимо)
            self.scroll_to_bottom()

            # Извлечение ссылок на продукты
            self.product_links = self.get_product_links()

        finally:
            self.auth_manager.close()
            return self.product_links

    def navigate_to_section(self, section_url):
        """Переход к определенной секции на сайте."""
        self.auth_manager.driver.get(section_url)
        # Ждем загрузки страницы
        try:
            WebDriverWait(self.auth_manager.driver, 60).until(
                EC.presence_of_element_located((By.CLASS_NAME, "MuiBox-root"))
            )
            logging.info(f"Перешли к секции: {section_url}")
        except TimeoutException:
            logging.error(f"Не удалось загрузить секцию: {section_url}")

    def scroll_to_bottom(self):
        """Прокрутка страницы до конца для подгрузки динамического контента."""
        last_height = self.auth_manager.driver.execute_script("return document.body.scrollHeight")
        while True:
            self.auth_manager.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Подождите, пока контент загрузится
            new_height = self.auth_manager.driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

    def get_product_links(self):
        """Извлечение всех ссылок на продукты со страницы."""
        product_links = set()  # Используем set для избежания дубликатов

        try:
            # Ждем, пока все элементы продуктов загрузятся (зависит от структуры страницы)
            WebDriverWait(self.auth_manager.driver, 20).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.MuiLink-root"))
            )
            logging.info("Элементы продуктов найдены на странице.")
        except TimeoutException:
            logging.error("Элементы продуктов не загрузились вовремя.")
            return list(product_links)

        # Извлекаем все <a> элементы с классом 'MuiLink-root'
        links = self.auth_manager.driver.find_elements(By.CSS_SELECTOR, "a.MuiLink-root")

        for link in links:
            href = link.get_attribute('href')
            if href and "/products/" in href and "completed" not in href:
                product_links.add(href)

        logging.info(f"Найдено {len(product_links)} уникальных ссылок на продукты.")
        return list(product_links)


class FreeProductParser:
    def __init__(self, link):
        self.auth_manager = AuthManager()
        self.free_product_links = list()
        self.link = link

    def run_checker(self):
        """Метод автоматизации."""
        logging.basicConfig(level=logging.INFO)

        try:
            self.auth_manager.login()

            if self.check_free_product():
                # проверка игры и отправка
                game_name = self.check_game_name()
                return game_name
            else:
                return False

        finally:
            self.auth_manager.close()

    def check_game_name(self):
        try:
            # Ждем загрузки элемента кнопки
            p_text = WebDriverWait(self.auth_manager.driver, 20).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "p.MuiTypography-root.MuiTypography-body1.mui-style-16yhggu"))
            )
            text = p_text.text.strip()
            logging.info(f"Название игры: {text}")
            return text
        except TimeoutException:
            logging.error(f"Название игры не загрузилось вовремя на странице: {self.link}")
        except Exception as e:
            logging.error(f"Ошибка при проверке игры {self.link}: {e}")

        return None  # Возвращаем None, если текст не найден или произошла ошибка

    def check_free_product(self):
        self.auth_manager.driver.get(self.link)

        try:
            # Ждем загрузки элемента кнопки
            button = WebDriverWait(self.auth_manager.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button.MuiBox-root.mui-style-qps1hq"))
            )
            text = button.text.strip()
            logging.info(f"Текст кнопки: {text}")

            if "Обычный" in text:
                return self.link  # Возвращаем ссылку, если текст найден
        except TimeoutException:
            logging.error(f"Кнопка не загрузилась вовремя на странице: {self.link}")
        except Exception as e:
            logging.error(f"Ошибка при проверке ссылки {self.link}: {e}")

        return None  # Возвращаем None, если текст не найден или произошла ошибка


def run_bot(link, delay=0):
    """Функция для запуска бота с возможной задержкой и обработкой ошибок"""
    if delay > 0:
        time.sleep(delay)  # Задержка перед началом

    bot = FreeProductParser(link)
    try:
        return bot.run_checker()
    except Exception as e:
        logging.error(f"Общая ошибка при обработке: {e}")


def main(links):
    exist_free_cards = {}
    results = []  # Список для хранения задач

    # Настройка multiprocessing.Pool
    max_processes = 5  # Максимальное количество параллельных процессов

    with multiprocessing.Pool(processes=max_processes) as pool:
        for link in links:
            delay = random.uniform(1, 10)
            result_game = pool.apply_async(run_bot, args=(link, delay))
            results.append((link, result_game))  # Сохраняем задачи в список

        pool.close()
        pool.join()  # Ожидаем завершения всех процессов

    # Получаем результаты после завершения всех процессов
    for link, result_game in results:
        if result_game.get():
            exist_free_cards[link] = result_game.get()

    logging.info(f"Все процессы нахождения бесплатных карточек завершены.")
    return exist_free_cards



# # Пример использования класса
# if __name__ == "__main__":
#     playerok_automation = ProductParser()
#     links = playerok_automation.run_parser()
#     exist_free_cards = main(links)
#     logging.info(f"Найденные бесплатные карточки: {exist_free_cards}")
