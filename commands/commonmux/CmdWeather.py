import requests
from datetime import datetime, timedelta
import pytz
import ephem
from evennia.utils.ansi import ANSIString
from evennia import default_cmds
from evennia.commands.default.muxcommand import MuxCommand
from world.utils import ansi_utils
from django.conf import settings
from world.utils.formatting import header, footer, section_header
import re

class CmdWeather(MuxCommand):
    """
    Get the current time, weather, moon phase, and tide information for San Diego.
    Admins can set a custom weather description for special events.

    Usage:
      +weather
      +weather/set <custom weather description>
      +weather/clear

    Switches:
      /set   - Set a custom weather description (Admin only)
      /clear - Clear the custom weather description (Admin only)
    """

    key = "+weather"
    aliases = ["+time", "weather"]
    locks = "cmd:all()"
    help_category = "Roleplaying Tools"

    def get_moon_phase(self):
        moon = ephem.Moon()
        moon.compute()
        phase = moon.phase
        if phase < 6.25:
            return "New Moon"
        elif phase < 43.75:
            return "Waxing Crescent"
        elif phase < 56.25:
            return "First Quarter"
        elif phase < 93.75:
            return "Waxing Gibbous"
        elif phase < 106.25:
            return "Full Moon"
        elif phase < 143.75:
            return "Waning Gibbous"
        elif phase < 156.25:
            return "Last Quarter"
        else:
            return "Waning Crescent"

    def get_wind_direction(self, degrees):
        if degrees is None:
            return "variable"
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                      "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / (360. / len(directions))) % len(directions)
        return directions[index]

    def get_tide_info(self):
        san_diego_tz = pytz.timezone('America/Los_Angeles')
        tide_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=today&station=9410170&product=predictions&datum=STND&time_zone=lst_ldt&interval=hilo&units=english&format=json"

        def _placeholder_tides():
            now = datetime.now(san_diego_tz)
            return [
                ("High", (now + timedelta(hours=2)).strftime("%I:%M %p"), "N/A"),
                ("Low", (now + timedelta(hours=8)).strftime("%I:%M %p"), "N/A"),
            ]

        try:
            response = requests.get(tide_url, timeout=15)
            response.raise_for_status()
            tide_data = response.json()

            if "predictions" not in tide_data:
                return []

            predictions = tide_data["predictions"]
            now = datetime.now(san_diego_tz)

            future_tides = [
                tide
                for tide in predictions
                if san_diego_tz.localize(datetime.strptime(tide["t"], "%Y-%m-%d %H:%M")) > now
            ]

            formatted_tides = []
            for tide in future_tides[:2]:
                tide_time = san_diego_tz.localize(datetime.strptime(tide["t"], "%Y-%m-%d %H:%M"))
                tide_type = "High" if tide["type"] == "H" else "Low"
                formatted_tides.append((
                    tide_type,
                    tide_time.strftime("%I:%M %p"),
                    f"{float(tide['v']):.1f} ft",
                ))

            return formatted_tides if formatted_tides else _placeholder_tides()

        except (requests.RequestException, ValueError, KeyError, TypeError):
            return _placeholder_tides()

    def func(self):
        if "set" in self.switches:
            if not self.caller.check_permstring("Admin"):
                self.caller.msg("You don't have permission to set custom weather.")
                return
            if not self.args:
                self.caller.msg("Usage: +weather/set <custom weather description>")
                return
            # Replace %r, %R with |/ and %t, %T with |-
            custom_weather = re.sub(r'%[rR]', '|/', self.args)
            custom_weather = re.sub(r'%[tT]', '|-', custom_weather)
            self.caller.db.custom_weather = custom_weather
            self.caller.msg(f"Custom weather set to: {custom_weather}")
            return

        if "clear" in self.switches:
            if not self.caller.check_permstring("Admin"):
                self.caller.msg("You don't have permission to clear custom weather.")
                return
            self.caller.attributes.remove("custom_weather")
            self.caller.msg("Custom weather cleared.")
            return

        # Check for custom weather override
        custom_weather = self.caller.db.custom_weather

        # Set the timezone for San Diego
        san_diego_tz = pytz.timezone('America/Los_Angeles')
        
        # IC: same Pacific calendar / clock as the server, year 2076
        now = datetime.now(san_diego_tz).replace(year=2076)
        current_date = now.strftime("%A, %B %d, %Y")
        current_time = now.strftime("%I:%M %p")

        width = 78
        output = []
        output.append(header(f"{settings.SERVERNAME} Weather", width=width, fillchar="="))
        output.append(self.format_stat("Date", current_date, width=width))
        output.append(self.format_stat("Time", current_time, width=width))

        if custom_weather:
            output.append(section_header("Custom Weather", width=width))
            wrapped_weather = ansi_utils.wrap_ansi(custom_weather, width=width)
            output.extend(wrapped_weather.split('\n'))
        else:
            # OpenWeatherMap API call
            api_key = "4a936d02adce57315006f55dde4e4e9c"
            city_id = "5393081"  # San Luis Obispo city ID, roughly where Night City is.
            url = f"http://api.openweathermap.org/data/2.5/weather?id={city_id}&appid={api_key}&units=imperial"
            forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?id={city_id}&appid={api_key}&units=imperial"
            
            try:
                response = requests.get(url, timeout=15)
                forecast_response = requests.get(forecast_url, timeout=15)
                data = response.json()
                forecast_data = forecast_response.json()

                if (
                    response.status_code == 200
                    and forecast_response.status_code == 200
                    and "main" in data
                    and data.get("weather")
                ):
                    temp = data["main"]["temp"]
                    feels_like = data["main"]["feels_like"]
                    humidity = data["main"]["humidity"]
                    description = data["weather"][0]["description"]
                    wind = data.get("wind") or {}
                    wind_speed = wind.get("speed", 0.0)
                    wind_deg = wind.get("deg")
                    wind_dir = self.get_wind_direction(wind_deg)

                    sunrise = datetime.fromtimestamp(data["sys"]["sunrise"], san_diego_tz).strftime("%I:%M %p")
                    sunset = datetime.fromtimestamp(data["sys"]["sunset"], san_diego_tz).strftime("%I:%M %p")

                    moon_phase = self.get_moon_phase()

                    tlist = forecast_data.get("list") or []
                    tomorrow = tlist[8] if len(tlist) > 8 else (tlist[-1] if tlist else None)

                    tide_info = self.get_tide_info()

                    output.append(self.format_stat("Weather", description.capitalize(), width=width))
                    output.append(self.format_stat("Temperature", f"{temp:.1f}F", "Feels Like", f"{feels_like:.1f}F", width=width))
                    output.append(self.format_stat("Humidity", f"{humidity}%", "Wind", f"{wind_speed:.1f} mph from the {wind_dir}", width=width))
                    output.append(self.format_stat("Sunrise", sunrise, "Sunset", sunset, width=width))
                    output.append(self.format_stat("Moon Sign", moon_phase, width=width))

                    output.append(section_header("Tide Information", width=width))
                    for tide in tide_info:
                        output.append(self.format_stat(f"{tide[0]} Tide", f"{tide[1]} ({tide[2]})", width=width))

                    if tomorrow and tomorrow.get("main") and tomorrow.get("weather"):
                        tomorrow_temp = tomorrow["main"]["temp"]
                        output.append(section_header("Tomorrow's Forecast", width=width))
                        forecast = f"{tomorrow['weather'][0]['description'].capitalize()}, {tomorrow_temp:.1f}F"
                        output.append(self.format_stat("", forecast, width=width))
                else:
                    err = data.get("message") or forecast_data.get("message") or "weather API error"
                    output.append(self.format_stat("Weather", f"Unavailable: {err}", width=width))

            except (requests.RequestException, ValueError, KeyError, TypeError):
                output.append(self.format_stat("Weather", "Unavailable (could not reach weather service)", width=width))

        output.append(footer(width=width, fillchar="="))
        
        # Send the formatted output to the player
        self.caller.msg("\n".join(output))

    def format_stat(self, stat1, value1, stat2=None, value2=None, width=78):
        half_width = width // 2
        stat1_str = f"|w{stat1:<12}|n" if stat1 else ""
        value1_str = f"{value1:<15}"
        
        if stat2 and value2:
            stat2_str = f"|w{stat2:<12}|n"
            value2_str = f"{value2:<15}"
            return f"{stat1_str}{value1_str}{stat2_str}{value2_str}"
        else:
            full_line = f"{stat1_str}{value1_str}"
            return ansi_utils.wrap_ansi(full_line, width=width)
