import multiprocessing
import random
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sys
import logging

from auth_manager import AuthManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("automation.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)


class DeleteManager:
    def __init__(self, auth_manager, link):
        self.auth_manager = auth_manager
        self.link = link

    def start_delete(self):
        """Выполнение действий на странице продажи."""
        url = self.link + "/edit"

        try:
            self.auth_manager.driver.get(url)
        except Exception as e:
            logging.error(f"Не удалось открыть страницу редактирования: {e}")
            return

        # Ожидание загрузки страницы
        wait = WebDriverWait(self.auth_manager.driver, 35)
        self.click_button_delete(wait)
        logging.info(f"Карточка успешно удалена.")

    def click_button_delete(self, wait):
        """Выставление карточки."""
        try:
            delete_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//button[@type='button' and text()='Удалить']"))
            )
            delete_button.click()
            logging.info("Кнопка 'Удалить' нажата.")

            button_confirm = wait.until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.MuiBox-root.mui-style-650qjg"))
            )
            button_confirm.click()
            logging.info("Кнопка 'Удалить' подтверждена.")
        except Exception as e:
            logging.error(f"Не удалось нажать кнопку 'Удалить': {e}")


def run_bot(link, delay=0):
    """Функция для запуска бота с возможной задержкой и обработкой ошибок"""
    if delay > 0:
        logging.info(f"Задержка перед запуском удаления карточки на {delay:.2f} секунд.")
        time.sleep(delay)  # Задержка перед началом

    auth_manager = AuthManager()
    bot = DeleteManager(auth_manager, link)
    try:
        auth_manager.login()
        bot.start_delete()
    except Exception as e:
        logging.error(f"Общая ошибка при обработке карточки: {e}")
    finally:
        auth_manager.close()


def main(links):
    max_processes = 5

    with multiprocessing.Pool(processes=max_processes) as pool:
        for link in links:
            delay = random.uniform(1, 15)
            pool.apply_async(run_bot, args=(link, delay))

        pool.close()
        pool.join()

    logging.info("Все процессы завершены.")
