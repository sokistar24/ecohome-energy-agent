Project Instructions
Your starter folder has the following structure:

ecohome_solution/

├── models/
│   ├── __init__.py
│   └── energy.py              # Database models for energy data
├── data/
│   ├── documents/
│   │   ├── tip_device_best_practices.txt
│   │   └── tip_energy_savings.txt
│   ├── energy_data.db         # SQLite database (created after setup)
│   └── vectorstore/           # ChromaDB vector store (created after setup)
├── agent.py                   # Main Energy Advisor agent
├── tools.py                   # Agent tools (weather, pricing, database, RAG)
├── requirements.txt           # Python dependencies
├── 01_db_setup.ipynb          # Database setup and sample data
├── 02_rag_setup.ipynb         # RAG pipeline setup
├── 03_run_and_evaluate.ipynb  # Agent testing and evaluation
└── README.md                  # Project documentation
Setup Phase
Run notebook 01_db_setup.ipynb to initialize the database and populate it with sample energy usage and solar generation data.
Run notebook 02_rag_setup.ipynb to set up the RAG pipeline with energy-saving tips and best practices.
Expand the knowledge base by adding at least 5 additional energy-saving documents to the data/documents/ folder. Make sure you have diverse topics covering:
HVAC optimization strategies
Smart home automation tips
Renewable energy integration
Seasonal energy management
Energy storage optimization
Agent Development
Review the existing tools in tools.py to understand the available capabilities.
Enhance the agent in agent.py by:
Creating comprehensive system instructions for the Energy Advisor.
Implementing proper error handling.
Adding context awareness for better recommendations.
Test and evaluate your agent using the scenarios in 03_run_and_evaluate.ipynb.
Key Features to Implement
Weather Integration: Use weather forecasts to predict solar generation and optimize device scheduling
Dynamic Pricing: Consider time-of-day electricity prices for cost optimization
Historical Analysis: Query past energy usage patterns for personalized advice
RAG Pipeline: Retrieve relevant energy-saving tips and best practices
Multi-device Optimization: Handle EVs, HVAC, appliances, and solar systems
Cost Calculations: Provide specific savings estimates and ROI analysis
Example Questions Your Agent Should Handle
"When should I charge my electric car tomorrow to minimize cost and maximize solar power?"
"What temperature should I set my thermostat on Wednesday afternoon if electricity prices spike?"
"Suggest three ways I can reduce energy use based on my usage history."
"How much can I save by running my dishwasher during off-peak hours?"
"What's the best time to run my pool pump this week based on the weather forecast?"
Submission Instructions
You're receiving the starter code, but please submit your project with all artifacts under ecohome_solution/ . We'll not look into ecohome_starter/ . Make sure you are copying and pasting the code from ecohome_starter/ to ecohome_solution/ before modifying it.

If you have installed a package, share the name and version in the documentation. Ideally share your requirements.txt and Python version, if you're developing locally.