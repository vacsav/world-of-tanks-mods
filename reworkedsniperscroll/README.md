# Reworked Sniper Scroll

<p align="center">
	&bull; <a href="#en">EN</a> &bull; <a href="#ru">RU</a> 
</p>

## EN

Allows you to use the `<scrollSensitivity>` value from the config file to change the number of steps when switching between `xZoom` values.

Configuration file location:

- WoT = `%APPDATA%\Wargaming.net\WorldOfTanks\preferences.xml`
- MT = `%APPDATA%\Lesta\MirTankov\preferences.xml`

Inside the config file:

```xml
<sniperMode>
	<camera>
		<scrollSensitivity> 1.000000 </scrollSensitivity> # Int and float value from 1 to 10, where the value determines the number of mouse wheel scrolling steps to switch between x2 and x4, etc.
	</camera>
</sniperMode>
```

## RU

Позволяет использовать из конфиг файла значение `<scrollSensitivity>` для изменения кол-ва отсечек при переходе между значениями `xZoom`.

Расположение конфиг файла:

- WoT = `%APPDATA%\Wargaming.net\WorldOfTanks\preferences.xml`
- MT = `%APPDATA%\Lesta\MirTankov\preferences.xml`

Внутри конфиг файла:

```xml
<sniperMode>
	<camera>
		<scrollSensitivity> 1.000000 </scrollSensitivity> # Целые и дробные значение от 1 до 10, где значение определяет кол-во отсечек колеса мыши для перехода между x2 и x4 и т.д.
	</camera>
</sniperMode>
```