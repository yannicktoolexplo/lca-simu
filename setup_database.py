from sqlalchemy import create_engine, MetaData, Table, Column, Integer, Float, String, Boolean, ForeignKey

# 1. Créer une base SQLite
engine = create_engine('sqlite:///simchain.db')
metadata = MetaData()

# 2. Définir la structure des tables
production_line = Table('production_line', metadata,
    Column('id', Integer, primary_key=True),
    Column('location', String),
    Column('hours', Integer),
    Column('days', Integer),
    Column('aluminium_capacity', Integer),
    Column('initial_aluminium', Integer),
    Column('foam_capacity', Integer),
    Column('initial_foam', Integer),
    Column('fabric_capacity', Integer),
    Column('initial_fabric', Integer),
    Column('paint_capacity', Integer),
    Column('initial_paint', Integer)
)

scenario = Table('scenario', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('include_supply', Boolean),
    Column('include_storage', Boolean)
)

result = Table('result', metadata,
    Column('id', Integer, primary_key=True),
    Column('scenario_id', Integer, ForeignKey('scenario.id')),
    Column('site', String),
    Column('total_production', Float),
    Column('total_cost', Float),
    Column('total_co2', Float)
)

# 3. Créer les tables dans la base
metadata.create_all(engine)