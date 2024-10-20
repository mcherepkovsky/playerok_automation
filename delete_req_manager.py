import json
import sys
import logging
import time
from concurrent.futures import as_completed
from concurrent.futures.thread import ThreadPoolExecutor
from random import uniform

import cloudscraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("automation.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)


class DeleteReqManager:
    def __init__(self, cookies_file='cookies_data.ckjson'):
        self.cookies_file = cookies_file
        self.cookies = self.load_cookies_from_file()
        self.scraper = cloudscraper.create_scraper()
        self.graphql_url = "https://playerok.com/graphql"
        self.user_id = self.get_my_id()
        self.slugs = self.get_all_slugs()

    def load_cookies_from_file(self):
        """Загрузка куки из JSON-файла и приведение к нужному формату"""
        with open(self.cookies_file, 'r') as f:
            cookies = json.load(f)
        # Приведение куки к строковому формату для заголовка
        return '; '.join([f"{cookie['name']}={cookie['value']}" for cookie in cookies])

    def extract_id(self, response_text):
        # Преобразуем текст ответа в словарь
        response_data = json.loads(response_text)

        # Извлекаем id пользователя
        user_id = response_data['data']['viewer']['id']

        return user_id

    def extract_slugs(self, response_text):
        """Извлечение всех slugs из ответа"""
        response_data = json.loads(response_text)
        slugs = [edge['node']['slug'] for edge in response_data['data']['items']['edges']]
        return slugs

    def extract_priority_and_game_name(self, response_text):
        """Извлечение priority и названия игры из ответа"""
        response_data = json.loads(response_text)
        card_id = response_data['data']['item']['id']
        priority = response_data['data']['item']['priority']
        game_name = response_data['data']['item']['game']['name']
        return card_id, priority, game_name

    def fetch_existing_cards(self):
        """Получение всех существующих карточек с их приоритетом и названием игры"""
        exist_cards = {}
        for slug in self.slugs:
            game_name, card_id = self.get_card_inf(slug)
            if game_name:
                exist_cards[card_id] = game_name
        return exist_cards

    def get_my_id(self):
        """Получение ID пользователя"""
        headers = self.get_common_headers()

        data = {
            "operationName": "viewer",
            "variables": {},
            "query": "query viewer {\n  viewer {\n    ...Viewer\n    __typename\n  }\n}\n\nfragment Viewer on User {\n  id\n  username\n  email\n  role\n  hasFrozenBalance\n  supportChatId\n  systemChatId\n  unreadChatsCounter\n  isBlocked\n  isBlockedFor\n  createdAt\n  profile {\n    id\n    avatarURL\n    __typename\n  }\n  __typename\n}"}

        response = self.scraper.post(self.graphql_url, headers=headers, json=data)

        # Проверяем статус ответа
        if response.status_code == 200:
            self.user_id = self.extract_id(response.text)
        else:
            logging.error(f"Ошибка получения UserID: {response.status_code}, {response.text}")

        return self.user_id

    def get_all_slugs(self):
        """Получение slug всех карточек"""
        headers = self.get_common_headers()

        data = {
            "operationName": "items",
            "variables": {
                "pagination": {"first": 16},
                "filter": {
                    "userId": self.user_id,
                    "status": ["APPROVED", "PENDING_MODERATION", "PENDING_APPROVAL"]}
            },
            "query": "query items($filter: ItemFilter, $pagination: Pagination) {\n  items(filter: $filter, pagination: $pagination) {\n    ...ItemProfileList\n    __typename\n  }\n}\n\nfragment ItemProfileList on ItemProfileList {\n  edges {\n    ...ItemEdgeFields\n    __typename\n  }\n  pageInfo {\n    startCursor\n    endCursor\n    hasPreviousPage\n    hasNextPage\n    __typename\n  }\n  totalCount\n  __typename\n}\n\nfragment ItemEdgeFields on ItemProfileEdge {\n  cursor\n  node {\n    ...ItemEdgeNode\n    __typename\n  }\n  __typename\n}\n\nfragment ItemEdgeNode on ItemProfile {\n  ...MyItemEdgeNode\n  ...ForeignItemEdgeNode\n  __typename\n}\n\nfragment MyItemEdgeNode on MyItemProfile {\n  id\n  slug\n  priority\n  status\n  name\n  price\n  rawPrice\n  statusExpirationDate\n  sellerType\n  attachment {\n    ...PartialFile\n    __typename\n  }\n  user {\n    ...UserItemEdgeNode\n    __typename\n  }\n  approvalDate\n  createdAt\n  priorityPosition\n  __typename\n}\n\nfragment PartialFile on File {\n  id\n  url\n  __typename\n}\n\nfragment UserItemEdgeNode on UserFragment {\n  ...UserEdgeNode\n  __typename\n}\n\nfragment UserEdgeNode on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment RegularUserFragment on UserFragment {\n  id\n  username\n  role\n  avatarURL\n  isOnline\n  isBlocked\n  rating\n  testimonialCounter\n  createdAt\n  supportChatId\n  systemChatId\n  __typename\n}\n\nfragment ForeignItemEdgeNode on ForeignItemProfile {\n  id\n  slug\n  priority\n  status\n  name\n  price\n  rawPrice\n  sellerType\n  attachment {\n    ...PartialFile\n    __typename\n  }\n  user {\n    ...UserItemEdgeNode\n    __typename\n  }\n  approvalDate\n  priorityPosition\n  createdAt\n  __typename\n}"}

        # Отправка POST-запроса на удаление товара
        response = self.scraper.post(self.graphql_url, headers=headers, json=data)

        # Проверяем статус ответа
        if response.status_code == 200:
            self.slugs = self.extract_slugs(response.text)
        else:
            logging.error(f"Ошибка получения всех slugs: {response.status_code}, {response.text}")

        return self.slugs

    def get_card_inf(self, slug):
        referer_url = "https://playerok.com/products/" + slug
        headers = self.get_common_headers()
        headers['Referer'] = referer_url
        data = {
            "operationName": "item",
            "variables": {
                "slug": slug
            },
            "query": "query item($slug: String, $id: UUID) {\n  item(slug: $slug, id: $id) {\n    ...RegularItem\n    __typename\n  }\n}\n\nfragment RegularItem on Item {\n  ...RegularMyItem\n  ...RegularForeignItem\n  __typename\n}\n\nfragment RegularMyItem on MyItem {\n  ...ItemFields\n  priority\n  sequence\n  priorityPrice\n  statusExpirationDate\n  comment\n  viewsCounter\n  statusDescription\n  editable\n  statusPayment {\n    ...StatusPaymentTransaction\n    __typename\n  }\n  moderator {\n    id\n    username\n    __typename\n  }\n  approvalDate\n  deletedAt\n  createdAt\n  updatedAt\n  mayBePublished\n  __typename\n}\n\nfragment ItemFields on Item {\n  id\n  slug\n  name\n  description\n  rawPrice\n  price\n  attributes\n  status\n  priorityPosition\n  sellerType\n  user {\n    ...ItemUser\n    __typename\n  }\n  buyer {\n    ...ItemUser\n    __typename\n  }\n  attachments {\n    ...PartialFile\n    __typename\n  }\n  category {\n    ...RegularGameCategory\n    __typename\n  }\n  game {\n    ...RegularGameProfile\n    __typename\n  }\n  comment\n  dataFields {\n    ...GameCategoryDataFieldWithValue\n    __typename\n  }\n  obtainingType {\n    ...GameCategoryObtainingType\n    __typename\n  }\n  __typename\n}\n\nfragment ItemUser on UserFragment {\n  ...UserEdgeNode\n  __typename\n}\n\nfragment UserEdgeNode on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment RegularUserFragment on UserFragment {\n  id\n  username\n  role\n  avatarURL\n  isOnline\n  isBlocked\n  rating\n  testimonialCounter\n  createdAt\n  supportChatId\n  systemChatId\n  __typename\n}\n\nfragment PartialFile on File {\n  id\n  url\n  __typename\n}\n\nfragment RegularGameCategory on GameCategory {\n  id\n  slug\n  name\n  categoryId\n  gameId\n  obtaining\n  options {\n    ...RegularGameCategoryOption\n    __typename\n  }\n  props {\n    ...GameCategoryProps\n    __typename\n  }\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  useCustomObtaining\n  autoConfirmPeriod\n  autoModerationMode\n  __typename\n}\n\nfragment RegularGameCategoryOption on GameCategoryOption {\n  id\n  group\n  label\n  type\n  field\n  value\n  sequence\n  valueRangeLimit {\n    min\n    max\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryProps on GameCategoryPropsObjectType {\n  minTestimonials\n  __typename\n}\n\nfragment RegularGameProfile on GameProfile {\n  id\n  name\n  type\n  slug\n  logo {\n    ...PartialFile\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryDataFieldWithValue on GameCategoryDataFieldWithValue {\n  id\n  label\n  type\n  inputType\n  copyable\n  hidden\n  required\n  value\n  __typename\n}\n\nfragment GameCategoryObtainingType on GameCategoryObtainingType {\n  id\n  name\n  description\n  gameCategoryId\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  sequence\n  __typename\n}\n\nfragment StatusPaymentTransaction on Transaction {\n  id\n  operation\n  direction\n  providerId\n  status\n  statusDescription\n  statusExpirationDate\n  value\n  props {\n    paymentURL\n    __typename\n  }\n  __typename\n}\n\nfragment RegularForeignItem on ForeignItem {\n  ...ItemFields\n  __typename\n}"
        }

        # Отправка POST-запроса на удаление товара
        response = self.scraper.post(self.graphql_url, headers=headers, json=data)

        # Проверяем статус ответа
        if response.status_code == 200:
            card_id, priority, game_name = self.extract_priority_and_game_name(response.text)
            if priority == "CUSTOM":
                return game_name, card_id
            else:
                return None
        else:
            logging.error(f"Ошибка проверки карточки: {response.status_code}, {response.text}")

    def delete_card(self, card_id, retries=3):
        headers = self.get_common_headers()
        data = {
            "operationName": "removeItem",
            "variables": {"id": card_id},
            "query": "mutation removeItem($id: UUID!) {\n  removeItem(id: $id) {\n    ...RegularItem\n    __typename\n  }\n}\n\nfragment RegularItem on Item {\n  ...RegularMyItem\n  ...RegularForeignItem\n  __typename\n}\n\nfragment RegularMyItem on MyItem {\n  ...ItemFields\n  priority\n  sequence\n  priorityPrice\n  statusExpirationDate\n  comment\n  viewsCounter\n  statusDescription\n  editable\n  statusPayment {\n    ...StatusPaymentTransaction\n    __typename\n  }\n  moderator {\n    id\n    username\n    __typename\n  }\n  approvalDate\n  deletedAt\n  createdAt\n  updatedAt\n  mayBePublished\n  __typename\n}\n\nfragment ItemFields on Item {\n  id\n  slug\n  name\n  description\n  rawPrice\n  price\n  attributes\n  status\n  priorityPosition\n  sellerType\n  user {\n    ...ItemUser\n    __typename\n  }\n  buyer {\n    ...ItemUser\n    __typename\n  }\n  attachments {\n    ...PartialFile\n    __typename\n  }\n  category {\n    ...RegularGameCategory\n    __typename\n  }\n  game {\n    ...RegularGameProfile\n    __typename\n  }\n  comment\n  dataFields {\n    ...GameCategoryDataFieldWithValue\n    __typename\n  }\n  obtainingType {\n    ...GameCategoryObtainingType\n    __typename\n  }\n  __typename\n}\n\nfragment ItemUser on UserFragment {\n  ...UserEdgeNode\n  __typename\n}\n\nfragment UserEdgeNode on UserFragment {\n  ...RegularUserFragment\n  __typename\n}\n\nfragment RegularUserFragment on UserFragment {\n  id\n  username\n  role\n  avatarURL\n  isOnline\n  isBlocked\n  rating\n  testimonialCounter\n  createdAt\n  supportChatId\n  systemChatId\n  __typename\n}\n\nfragment PartialFile on File {\n  id\n  url\n  __typename\n}\n\nfragment RegularGameCategory on GameCategory {\n  id\n  slug\n  name\n  categoryId\n  gameId\n  obtaining\n  options {\n    ...RegularGameCategoryOption\n    __typename\n  }\n  props {\n    ...GameCategoryProps\n    __typename\n  }\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  useCustomObtaining\n  autoConfirmPeriod\n  autoModerationMode\n  __typename\n}\n\nfragment RegularGameCategoryOption on GameCategoryOption {\n  id\n  group\n  label\n  type\n  field\n  value\n  sequence\n  valueRangeLimit {\n    min\n    max\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryProps on GameCategoryPropsObjectType {\n  minTestimonials\n  __typename\n}\n\nfragment RegularGameProfile on GameProfile {\n  id\n  name\n  type\n  slug\n  logo {\n    ...PartialFile\n    __typename\n  }\n  __typename\n}\n\nfragment GameCategoryDataFieldWithValue on GameCategoryDataFieldWithValue {\n  id\n  label\n  type\n  inputType\n  copyable\n  hidden\n  required\n  value\n  __typename\n}\n\nfragment GameCategoryObtainingType on GameCategoryObtainingType {\n  id\n  name\n  description\n  gameCategoryId\n  noCommentFromBuyer\n  instructionForBuyer\n  instructionForSeller\n  sequence\n  __typename\n}\n\nfragment StatusPaymentTransaction on Transaction {\n  id\n  operation\n  direction\n  providerId\n  status\n  statusDescription\n  statusExpirationDate\n  value\n  props {\n    paymentURL\n    __typename\n  }\n  __typename\n}\n\nfragment RegularForeignItem on ForeignItem {\n  ...ItemFields\n  __typename\n}"
        }

        for attempt in range(retries):
            # Пауза для снижения нагрузки на сервер
            time.sleep(uniform(0.5, 5) * (attempt + 1))  # Увеличение задержки при повторных попытках

            response = self.scraper.post(self.graphql_url, headers=headers, json=data)
            if response.status_code == 200:
                return f"Товар {card_id} успешно удален!"
            elif response.status_code == 429:
                logging.error(f"Слишком много запросов. Попытка {attempt + 1} из {retries}. Ждем...")
            elif response.status_code == 403:
                logging.error(f"Запрос заблокирован. Попытка {attempt + 1} из {retries}. Ждем...")
            else:
                return f"Ошибка при удалении товара {card_id}: {response.status_code}, {response.text}"

        return f"Не удалось удалить товар {card_id} после {retries} попыток"

    def delete_cards_parallel(self, card_ids, max_workers=5):
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_card = {executor.submit(self.delete_card, card_id, 3): card_id for card_id in card_ids}

            for future in as_completed(future_to_card):
                card_id = future_to_card[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append(f"Карточка {card_id} вызвала исключение: {exc}")

        return results

    def get_common_headers(self):
        return {
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
            "Apollo-Require-Preflight": "true",
            "Apollographql-Client-Name": "web",
            "Content-Type": "application/json",
            "Cookie": self.cookies,
        }

if __name__ == '__main__':
    mhg = DeleteReqManager()
    #x = mhg.get_all_slugs()
    print(mhg.delete_card("1ef8ee2d-75e7-66a0-84da-19234486a8a2"))
