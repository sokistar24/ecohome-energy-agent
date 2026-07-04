test_cases = [
    {
        "id": "ev_charging_solar",
        "question": "When should I charge my electric car tomorrow to minimise cost and maximise solar power?",
        "expected_tools": ["get_electricity_prices", "get_weather_forecast"],
        "expected_response": "Should recommend a specific charging time window, cite the cheap vs expensive price hours in GBP, and consider when solar generation peaks.",
    },
    {
        "id": "thermostat_peak",
        "question": "What temperature should I set my thermostat on Wednesday afternoon if electricity prices spike?",
        "expected_tools": ["get_electricity_prices", "search_energy_tips"],
        "expected_response": "Should give a specific temperature in °C, identify the peak price hours to avoid, and suggest pre-heating or setting back during the spike, backed by a best-practice tip.",
    },
    {
        "id": "dishwasher_offpeak_savings",
        "question": "How much can I save by running my dishwasher during off-peak hours instead of the evening peak?",
        "expected_tools": ["get_electricity_prices", "calculate_energy_savings"],
        "expected_response": "Should compare off-peak vs peak pricing, name the cheapest hours, and give a concrete £ savings estimate from the savings calculator.",
    },
    {
        "id": "pool_pump_weather",
        "question": "What's the best time to run my pool pump this week based on the weather forecast?",
        "expected_tools": ["get_weather_forecast", "get_electricity_prices", "search_energy_tips"],
        "expected_response": "Should recommend specific hours to run the pump, align them with sunny/high-solar periods and cheap pricing, and reference pool-pump best practices.",
    },
    {
        "id": "reduce_usage_history",
        "question": "Suggest three ways I can reduce my energy use based on my recent usage history.",
        "expected_tools": ["get_recent_energy_summary", "search_energy_tips"],
        "expected_response": "Should reference the customer's actual recent usage/device breakdown and give three specific, actionable reduction strategies drawn from the knowledge base.",
    },
    {
        "id": "battery_charge_source",
        "question": "Should I charge my home battery from solar or from the grid tonight, and when?",
        "expected_tools": ["get_electricity_prices", "get_weather_forecast", "search_energy_tips"],
        "expected_response": "Should advise charging from solar surplus by day vs cheap off-peak grid overnight, name the cheap hours, and recommend discharging during the evening peak, citing storage best practices.",
    },
    {
        "id": "appliance_scheduling_general",
        "question": "When during the day is the cheapest time to run my washing machine and tumble dryer?",
        "expected_tools": ["get_electricity_prices"],
        "expected_response": "Should identify the cheapest hours from the price data and recommend a specific off-peak window in GBP terms.",
    },
    {
        "id": "solar_maximization_tomorrow",
        "question": "How can I maximise the use of my own solar power tomorrow?",
        "expected_tools": ["get_weather_forecast", "search_energy_tips"],
        "expected_response": "Should use the forecast to identify peak solar hours (high irradiance), recommend shifting flexible loads into that window, and reference solar self-consumption tips.",
    },
    {
        "id": "ev_overnight_cost",
        "question": "What will it roughly cost to charge my EV overnight, and which hours are cheapest?",
        "expected_tools": ["get_electricity_prices", "calculate_energy_savings"],
        "expected_response": "Should name the cheapest overnight hours and provide an approximate charging cost or saving in GBP using the savings tool.",
    },
    {
        "id": "past_solar_generation",
        "question": "How much solar did I generate over the last week, and how can I use more of it?",
        "expected_tools": ["query_solar_generation", "search_energy_tips"],
        "expected_response": "Should report the actual solar generation from the database for the period and suggest specific ways to raise self-consumption from the knowledge base.",
    },
    {
        "id": "heating_cost_optimization",
        "question": "How can I cut my heating costs this winter without being cold?",
        "expected_tools": ["search_energy_tips", "get_electricity_prices"],
        "expected_response": "Should give specific °C thermostat guidance, recommend pre-heating in cheap hours and reducing during peak, and cite HVAC/seasonal best practices.",
    },
    {
        "id": "device_usage_breakdown",
        "question": "Which of my devices used the most energy recently, and what should I do about it?",
        "expected_tools": ["query_energy_usage", "search_energy_tips"],
        "expected_response": "Should identify the highest-consuming device(s) from the usage data and give targeted, device-specific reduction advice from the knowledge base.",
    },
]

if len(test_cases) < 10:
    raise ValueError("You MUST have at least 10 test cases")
