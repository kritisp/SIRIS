"""Initial S.I.R.I.S. domain schema migration

Revision ID: 001_initial_domain_schema
Revises: 
Create Date: 2026-08-28 15:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '001_initial_domain_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Enums
    person_role_enum = postgresql.ENUM('ACCUSED', 'SUSPECT', 'VICTIM', 'WITNESS', 'COMPLAINANT', 'OTHER', name='person_role_enum', create_type=False)
    person_role_enum.create(op.get_bind(), checkfirst=True)

    vehicle_role_enum = postgresql.ENUM('SUSPECT_VEHICLE', 'STOLEN_VEHICLE', 'RECOVERED_VEHICLE', 'VICTIM_VEHICLE', 'OTHER', name='vehicle_role_enum', create_type=False)
    vehicle_role_enum.create(op.get_bind(), checkfirst=True)

    evidence_type_enum = postgresql.ENUM('CCTV', 'MOBILE', 'DOCUMENT', 'VEHICLE', 'WEAPON', 'DIGITAL', 'PHYSICAL', 'OTHER', name='evidence_type_enum', create_type=False)
    evidence_type_enum.create(op.get_bind(), checkfirst=True)

    investigation_event_type_enum = postgresql.ENUM('FIR_REGISTERED', 'STATEMENT_RECORDED', 'EVIDENCE_COLLECTED', 'SUSPECT_IDENTIFIED', 'ARREST', 'SEARCH', 'INTERROGATION', 'CHARGESHEET_FILED', 'OTHER', name='investigation_event_type_enum', create_type=False)
    investigation_event_type_enum.create(op.get_bind(), checkfirst=True)

    # 2. Locations
    op.create_table(
        'locations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('locality', sa.String(length=100), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_locations_district', 'locations', ['district'])

    # 3. Persons
    op.create_table(
        'persons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('date_of_birth', sa.Date(), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('identifier_hash', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_persons_name', 'persons', ['name'])
    op.create_index('ix_persons_identifier_hash', 'persons', ['identifier_hash'])

    # 4. Vehicles
    op.create_table(
        'vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('registration_number', sa.String(length=100), nullable=False, unique=True),
        sa.Column('vehicle_type', sa.String(length=50), nullable=True),
        sa.Column('make', sa.String(length=100), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_vehicles_registration_number', 'vehicles', ['registration_number'])

    # 5. Phones
    op.create_table(
        'phones',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('normalized_number', sa.String(length=50), nullable=False, unique=True),
        sa.Column('number_hash', sa.String(length=128), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_phones_normalized_number', 'phones', ['normalized_number'])
    op.create_index('ix_phones_number_hash', 'phones', ['number_hash'])

    # 6. PersonPhones
    op.create_table(
        'person_phones',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('phones.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('person_id', 'phone_id', name='uq_person_phone')
    )
    op.create_index('ix_person_phones_person_id', 'person_phones', ['person_id'])
    op.create_index('ix_person_phones_phone_id', 'person_phones', ['phone_id'])

    # 7. Legal Sections
    op.create_table(
        'legal_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('code', sa.String(length=100), nullable=False, unique=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('law_name', sa.String(length=100), server_default='IPC', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_legal_sections_code', 'legal_sections', ['code'])
    op.create_index('ix_legal_sections_law_name', 'legal_sections', ['law_name'])

    # 8. Cases
    op.create_table(
        'cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('fir_number', sa.String(length=100), nullable=False, unique=True),
        sa.Column('police_station', sa.String(length=150), nullable=False),
        sa.Column('district', sa.String(length=150), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=False),
        sa.Column('registration_date', sa.Date(), nullable=False),
        sa.Column('incident_date', sa.Date(), nullable=True),
        sa.Column('incident_time', sa.Time(), nullable=True),
        sa.Column('crime_type', sa.String(length=150), nullable=False),
        sa.Column('crime_category', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='UNDER_INVESTIGATION', nullable=False),
        sa.Column('location_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('locations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_cases_fir_number', 'cases', ['fir_number'])
    op.create_index('ix_cases_crime_type', 'cases', ['crime_type'])
    op.create_index('ix_cases_crime_category', 'cases', ['crime_category'])
    op.create_index('ix_cases_registration_date', 'cases', ['registration_date'])
    op.create_index('ix_cases_incident_date', 'cases', ['incident_date'])
    op.create_index('ix_cases_district', 'cases', ['district'])
    op.create_index('ix_cases_police_station', 'cases', ['police_station'])
    op.create_index('ix_cases_location_id', 'cases', ['location_id'])

    # 9. CasePersons
    op.create_table(
        'case_persons',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('persons.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Enum('ACCUSED', 'SUSPECT', 'VICTIM', 'WITNESS', 'COMPLAINANT', 'OTHER', name='person_role_enum'), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('case_id', 'person_id', 'role', name='uq_case_person_role')
    )
    op.create_index('ix_case_persons_case_id', 'case_persons', ['case_id'])
    op.create_index('ix_case_persons_person_id', 'case_persons', ['person_id'])
    op.create_index('ix_case_person_role', 'case_persons', ['role'])

    # 10. CaseVehicles
    op.create_table(
        'case_vehicles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vehicle_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('vehicles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.Enum('SUSPECT_VEHICLE', 'STOLEN_VEHICLE', 'RECOVERED_VEHICLE', 'VICTIM_VEHICLE', 'OTHER', name='vehicle_role_enum'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('case_id', 'vehicle_id', 'role', name='uq_case_vehicle_role')
    )
    op.create_index('ix_case_vehicles_case_id', 'case_vehicles', ['case_id'])
    op.create_index('ix_case_vehicles_vehicle_id', 'case_vehicles', ['vehicle_id'])

    # 11. CasePhones
    op.create_table(
        'case_phones',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('phone_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('phones.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('case_id', 'phone_id', name='uq_case_phone')
    )
    op.create_index('ix_case_phones_case_id', 'case_phones', ['case_id'])
    op.create_index('ix_case_phones_phone_id', 'case_phones', ['phone_id'])

    # 12. Evidences
    op.create_table(
        'evidences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('evidence_type', sa.Enum('CCTV', 'MOBILE', 'DOCUMENT', 'VEHICLE', 'WEAPON', 'DIGITAL', 'PHYSICAL', 'OTHER', name='evidence_type_enum'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('collected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='COLLECTED', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_evidences_case_id', 'evidences', ['case_id'])
    op.create_index('ix_evidences_evidence_type', 'evidences', ['evidence_type'])

    # 13. Chargesheets
    op.create_table(
        'chargesheets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('filing_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='FILED', nullable=False),
        sa.Column('document_reference', sa.String(length=255), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_chargesheets_case_id', 'chargesheets', ['case_id'])

    # 14. InvestigationEvents
    op.create_table(
        'investigation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.Enum('FIR_REGISTERED', 'STATEMENT_RECORDED', 'EVIDENCE_COLLECTED', 'SUSPECT_IDENTIFIED', 'ARREST', 'SEARCH', 'INTERROGATION', 'CHARGESHEET_FILED', 'OTHER', name='investigation_event_type_enum'), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('event_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('officer_reference', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_investigation_events_case_id', 'investigation_events', ['case_id'])
    op.create_index('ix_investigation_events_event_type', 'investigation_events', ['event_type'])
    op.create_index('ix_investigation_events_event_date', 'investigation_events', ['event_date'])

    # 15. CaseLegalSections
    op.create_table(
        'case_legal_sections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('cases.id', ondelete='CASCADE'), nullable=False),
        sa.Column('legal_section_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('legal_sections.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('case_id', 'legal_section_id', name='uq_case_legal_section')
    )
    op.create_index('ix_case_legal_sections_case_id', 'case_legal_sections', ['case_id'])
    op.create_index('ix_case_legal_sections_legal_section_id', 'case_legal_sections', ['legal_section_id'])


def downgrade() -> None:
    op.drop_table('case_legal_sections')
    op.drop_table('investigation_events')
    op.drop_table('chargesheets')
    op.drop_table('evidences')
    op.drop_table('case_phones')
    op.drop_table('case_vehicles')
    op.drop_table('case_persons')
    op.drop_table('cases')
    op.drop_table('legal_sections')
    op.drop_table('person_phones')
    op.drop_table('phones')
    op.drop_table('vehicles')
    op.drop_table('persons')
    op.drop_table('locations')

    op.execute('DROP TYPE IF EXISTS investigation_event_type_enum')
    op.execute('DROP TYPE IF EXISTS evidence_type_enum')
    op.execute('DROP TYPE IF EXISTS vehicle_role_enum')
    op.execute('DROP TYPE IF EXISTS person_role_enum')
