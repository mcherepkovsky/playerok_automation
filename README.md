# Автоматизация управления карточками игр

Этот проект предназначен для автоматизации процесса создания и удаления карточек игр на различных серверах. С его помощью можно создавать карточки на основе пресетов и управлять их удалением как для отдельных игр, так и для всех игр на сервере.

## Установка и настройка

1. **Установка расширения для копирования cookies:**
   - Установите расширение для Chrome: [Copy Cookies](https://chromewebstore.google.com/detail/copy-cookies/jcbpglbplpblnagieibnemmkiamekcdg?hl=ro&authuser=0).
   
2. **Получение и настройка cookies:**
   - Перейдите на целевой сайт и нажмите на установленное расширение для копирования cookies сайта в буфер обмена.
   - Вставьте скопированные cookies в файл `data/cookies_data.ckjson`, не изменяя их содержимое.

3. **Рекомендации:**
   - Рекомендуется использовать VPN для избежания блокировки по IP-адресу. В проекте установлены задержки, но их, возможно, нужно будет настроить дополнительно.
   - Чем быстрее интернет-соединение, тем быстрее выполняется процесс.

## Работа с карточками

1. **Отсутствующие карточки:**
   - Если вы заметили, что после завершения работы какой-то карточки не хватает, проверьте её в завершённых — возможно, она осталась в виде черновика.

2. **Папка `chips`:**
   - В этой папке выберите нужную игру. Файл `presets.json` содержит карточки, которые вы составляете. Параметр `amount` должен совпадать с названием соответствующей картинки из папки `pictures`. Картинки поддерживаются в форматах PNG и JPG.

3. **Папка `data`:**
   - Файл `descriptions.json` содержит описания для игр по их названиям. Поле `product_data` отвечает за подробное описание товара.
   
4. **Создание карточек для игр:**
   - Для игры **Arizona** карточки выставляются на любой сервер.
   - Для игр с несколькими серверами — сначала создается одна карточка для всех серверов, потом следующая дял всех серверов и так далее в 3х потоках.

## Ограничения

- **Создание карточек Black Russia:** не выбирайте создание карточек для Black Russia — эта функция не работает. Однако вы можете использовать её для удаления карточек.

## Удаление карточек

1. Дождитесь, пока загрузятся все карточки.
2. Выберите нужную игру — программа удалит карточки только для этой игры.
3. Если выбрать опцию «Удалить все» — будут удалены карточки для всех игр.

## Примечания

- Убедитесь, что все необходимые файлы и изображения корректно добавлены, а данные в `presets.json` и других конфигурационных файлах соответствуют требованиям для успешного выполнения операций.
