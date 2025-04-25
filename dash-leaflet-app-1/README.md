# Dash Leaflet Vessel Tracking Application

This project is a web application built using Dash and the Leaflet library that allows users to visualize vessel data on an interactive map. Users can select a datetime period and a vessel name to view the last known positions of vessels from a PostgreSQL database.

## Project Structure

```
dash-leaflet-app
├── app.py                # Main application file
├── assets
│   └── styles.css       # Custom CSS styles for the application
├── data
│   └── db_config.json   # Database configuration details
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd dash-leaflet-app
   ```

2. **Install dependencies**:
   Make sure you have Python installed. Then, create a virtual environment and install the required packages:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   pip install -r requirements.txt
   ```

3. **Configure the database**:
   Update the `data/db_config.json` file with your PostgreSQL database credentials:
   ```json
   {
       "username": "your_username",
       "password": "your_password",
       "database": "your_database",
       "table": "your_table"
   }
   ```

4. **Run the application**:
   Execute the following command to start the Dash application:
   ```bash
   python app.py
   ```

5. **Access the application**:
   Open your web browser and go to `http://127.0.0.1:8050` to view the application.

## Usage Guidelines

- Select a datetime range using the provided input fields.
- Choose a vessel name from the dropdown list to filter the displayed data.
- The map will update to show the last known positions of the selected vessels, with different colors representing different vessels.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.