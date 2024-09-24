import yaml
from pathlib import Path
from pydantic import BaseModel as PydanticBaseModel
import pandas as pd
import sqlalchemy
from dotenv import load_dotenv, dotenv_values


class Config(PydanticBaseModel):
    """Basis functie om de configuratie in te laden.

    Parameters
    ----------
    config_path: Path
                 Pad naar een  `.yaml` bestand waarin per functie staat beschreven wat de in/ouput bestanden zijn

    """

    config_path: Path

    # elke functie heeft een dictionary met daar in de configuratie
    toegelaten_functies: set = {
        "WaardesKeerTwee",
        "WaardesDelenTwee",
        "global_variables",
    }
    WaardesKeerTwee: dict = {}
    WaardesDelenTwee: dict = {}
    global_variables: dict = {}

    #
    dump: dict = {}

    def lees_config(self):
        """Laad het gegeven pad in, zet de configuraties klaar in de Config class"""

        with self.config_path.open() as fin:
            data = yaml.safe_load(fin)

        for functie, configuratie in data.items():
            if functie in self.toegelaten_functies:
                setattr(self, functie, configuratie)
            else:  # als de functie niet is geconfigureerd: vang dat hier af
                self.dump.update({functie: configuratie})
                # TODO: self.logger(f"{functie} niet gevonden, kijk of deze functie bestaat")


class DataAdapter(PydanticBaseModel):
    """Basis DataAdapter"""

    config: Config
    input_types: dict = {}
    output_types: dict = {}

    def initialize_input_types(self):
        self.input_types["csv"] = self.input_csv
        self.input_types["postgresql_database"] = self.input_postgresql

    def initialize_output_types(self):
        self.output_types["csv"] = self.output_csv
        self.output_types["postgresql_database"] = self.output_postgresql

    def input(self, functie):
        """Gegeven het config, stuurt de juiste input waarde aan

        Parameters:
        -----------
        functie: str
                 naam van de functie die bij het bestands type hoort

        opties: dict
                  extra informatie die ook naar de functie moet om het bestand te lezen

        """
        # TODO: kan dit eleganters?
        self.initialize_input_types()  # maak een dictionary van type: functie
        # haal de input configuratie op van de functie
        functie_input_config = getattr(self.config, functie)["input"]
        # leid het data type af
        data_type = functie_input_config["type"]

        # path relative to rootdir specified in config
        if "path" in functie_input_config:
            functie_input_config["path"] = (
                Path(self.config.global_variables["rootdir"])
                / functie_input_config["path"]
            )

        # uit het .env bestand halen we de extra waardes en laden deze in de config
        if load_dotenv():
            environmental_variables = dict(dotenv_values())
        else:
            raise UserWarning("Ensure a `.env` file is present in the root directory")

        functie_input_config.update(environmental_variables)

        # roep de bijbehorende functie bij het data type aan en geef het input pad mee.
        bijbehorende_functie = self.input_types[data_type]
        df = bijbehorende_functie(functie_input_config)
        return df

    @staticmethod
    def input_csv(input_config):
        """Laat een csv bestand in gegeven een pad

        Returns:
        --------
        pd.Dataframe
        """
        # Data checks worden gedaan in de functies zelf, hier alleen geladen
        path = input_config["path"]
        df = pd.read_csv(path)
        return df

    @staticmethod
    def input_postgresql(input_config):
        """Schrijft data naar een postgresql database gegeven het pad naar een credential bestand.

        Parametes:
        ----------
        input_config: dict
                     in


        Notes:
        ------
        In de `.env` environment bestand moet staan:
        user: str
        password: str
        host: str
        port: str
        database: str
        schema: str



        Returns:
        --------
        pd.Dataframe

        """
        # TODO: doen we dit zo?
        table = input_config["table"]

        # maak verbinding object
        engine = sqlalchemy.create_engine(
            f"postgresql://{input_config['user']}:{input_config['password']}@{input_config['host']}:{input_config['port']}/{input_config['database']}"
        )

        query = f"SELECT objectid, objecttype, parameterid, datetime, value FROM {input_config['schema']}.{table};"

        # qurey uitvoeren op de database
        with engine.connect() as connection:
            df = pd.read_sql_query(sql=sqlalchemy.text(query), con=connection)

        # verbinding opruimen
        engine.dispose()

        return df

    def output(self, functie, df):
        """Gegeven het config, stuurt de juiste input waarde aan

        Parameters:
        -----------
        functie: str
                 naam van de functie die bij het bestands type hoort
        df: pd.Dataframe
            pandas dataframe om weg te schrijvne

        opties: dict
                extra informatie die ook naar de functie moet om het bestand te schrijven

        """
        # TODO: kan dit eleganters?
        self.initialize_output_types()  # maak een dictionary van type: functie
        # haal de input configuratie op van de functie
        functie_output_config = getattr(self.config, functie)["output"]
        # leid het data type af
        data_type = functie_output_config["type"]

        # path relative to rootdir specified in config
        if "path" in functie_output_config:
            functie_output_config["path"] = (
                Path(self.config.global_variables["rootdir"])
                / functie_output_config["path"]
            )

        # uit het .env bestand halen we de extra waardes en laden deze in de config
        if load_dotenv():
            environmental_variables = dict(dotenv_values())
        else:
            raise UserWarning("Ensure a `.env` file is present in the root directory")
        functie_output_config.update(environmental_variables)

        # roep de bijbehorende functie bij het data type aan en geef het input pad mee.
        bijbehorende_functie = self.output_types[data_type]
        df = bijbehorende_functie(functie_output_config, df)
        return df

    @staticmethod
    def output_csv(output_config, df):
        """schrijft een csv bestand in gegeven een pad

        Notes:
        ------
        Gebruikt hiervoor de pandas.DataFrame.to_csv
        Opties om dit aan te passen kunnen worden mee gegeven in het configuratie bestand.

        Returns:
        --------
        None
        """
        # Data checks worden gedaan in de functies zelf, hier alleen geladen

        # TODO: opties voor csv mogen alleen zijn wat er mee gegeven mag wroden aan .to_csv
        path = output_config["path"]
        df.to_csv(path)

    @staticmethod
    def output_postgresql(output_config, df):
        """Schrijft data naar een postgresql database gegeven het pad naar een credential bestand.

        Parametes:
        ----------
        df: pd.Dataframe
            dataframe met data om weg te schrijven
        opties: dict
                dictionary met extra opties waar onder:
                    schema: str
                            naam van het schema in de postgresql database
                    table: str
                        naam van de tabel in de postgresql database


        Notes:
        ------
        In het credential bestand moet staan:
        user: str
        password: str
        host: str
        port: str
        database: str


        Returns:
        --------
        None

        """
        table = output_config["table"]
        schema = output_config["schema"]

        engine = sqlalchemy.create_engine(
            f"postgresql://{output_config['user']}:{output_config['password']}@{output_config['host']}:{output_config['port']}/{output_config['database']}"
        )

        df.to_sql(
            table,
            con=engine,
            schema=schema,
            if_exists="replace",  # append
            index=False,
        )

        # verbinding opruimen
        engine.dispose()
