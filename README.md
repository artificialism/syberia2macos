# Русификатор Syberia 2 для Mac Silicon

Установщик и русификатор Syberia 2. Заранее скажу что из стима игра нативно не запускается, для запуска нужна ScummVM. Русификатор от Логруса (издан 1С).

## Установка
Требуются установленные Python 3.10+ и ScummVM
1. Закройте игру. В Steam оставьте язык English так как пакет заменяет английский слот.
2. Откройте папку `build/macos-ru` и запустите Install.command. 
3. Дождитесь сообщения `Installed 2236 resources`. Установщик покажет путь резервной копии. Не удаляйте папку пакета и backups
4. Добавьте в ScummVM папку Contents игры (`/Users/../Library/Application Support/Steam/steamapps/common/Syberia 2/Syberia 2.app/Contents`)
5. Запустите игру из ScummVM

Аналонично можно запустить все через консоль:
```sh
python3 "../syberia2macos/build/macos-ru/install.py" check
python3 "../syberia2macos/build/macos-ru/install.py" install
```

При нестандартном расположении игры добавьте `--app "/полный/путь/Syberia 2.app"`.

## Откат

Запустите Restore.command в папке пакета, он использует последнюю завершенную резервную копию для стандартного пути игры. Или укажите конкретную копию вручную:

```sh
python3 "/Users/maratkhisyametdinov/dev/syberia2rus/build/macos-ru/install.py" restore --backup "/полный/путь/из/сообщения/установщика"
```

Если Steam обновил или изменил заменённые файлы, автоматический откат откажется их перезаписывать. Проверка целостности игры через Steam восстанавливает официальные ресурсы

## Дополнительно

В исходной папке проекта:

```sh
python3 scripts/build_patch.py --audio --video-audio --output build/new-macos-ru
cp scripts/install_patch.py build/new-macos-ru/install.py
```

Альтернативный вариант кодировки:

```sh
python3 scripts/build_patch.py --encoding utf8 --audio --video-audio --output build/utf8-trial
cp scripts/install_patch.py build/utf8-trial/install.py
```
### UPD
Вроде это ласт мой потуг, за последнее время залил 3 репо на гитхаб, 2 вроде даже серьезные вполне. Честно без понятия кому это пригодится, ощущение что про Syberia знают/помнят и так полтора человека, а русификатор для силикон маков... Надеюсь кому-то все же это поможет!
