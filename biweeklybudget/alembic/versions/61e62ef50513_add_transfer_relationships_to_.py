"""add transfer relationships to transactions

Revision ID: 61e62ef50513
Revises: 32b34a664b5a
Create Date: 2017-10-26 16:13:27.227932

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Date, ForeignKey
from biweeklybudget.utils import dtnow
import logging

logger = logging.getLogger(__name__)

Session = sessionmaker()

Base = declarative_base()

# revision identifiers, used by Alembic.
revision = '61e62ef50513'
down_revision = '32b34a664b5a'
branch_labels = None
depends_on = None


class Transaction(Base):
    """
    Simplified Transaction model for the data migration...
    """

    __tablename__ = 'transactions'
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}
    )

    #: Primary Key
    id = Column(Integer, primary_key=True)

    #: date of the transaction
    date = Column(Date, default=dtnow().date())

    #: description
    description = Column(String(254), nullable=False, index=True)

    #: free-form notes
    notes = Column(String(254))

    #: ID of the account this transaction is against
    account_id = Column(Integer, ForeignKey('accounts.id'))

    #: ID of the Budget this transaction is against
    budget_id = Column(Integer, ForeignKey('budgets.id'))

    #: If the transaction is one half of a transfer, the Transaction ID of the
    #: other half/side of the transfer.
    transfer_id = Column(Integer, ForeignKey('transactions.id'))

    def __repr__(self):
        return "<Transaction(id=%s)>" % (
            self.id
        )


class Account(Base):

    __tablename__ = 'accounts'
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}
    )

    #: Primary Key
    id = Column(Integer, primary_key=True)


class ScheduledTransaction(Base):

    __tablename__ = 'scheduled_transactions'
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}
    )

    #: Primary Key
    id = Column(Integer, primary_key=True)


class Budget(Base):

    __tablename__ = 'budgets'
    __table_args__ = (
        {'mysql_engine': 'InnoDB'}
    )

    #: Primary Key
    id = Column(Integer, primary_key=True)


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        'transactions',
        sa.Column('transfer_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        op.f('fk_transactions_transfer_id_transactions'),
        'transactions',
        'transactions',
        ['transfer_id'],
        ['id']
    )
    bind = op.get_bind()
    session = Session(bind=bind)
    # begin data manipulation
    last_txn = None
    for txn in session.query(Transaction).filter(
        Transaction.description.like('Budget Transfer - %')
    ).order_by(Transaction.id.asc()).all():
        if last_txn is None:
            last_txn = txn
            continue
        if (
            txn.description == last_txn.description and
            txn.date == last_txn.date and
            txn.notes == last_txn.notes and
            txn.account_id == last_txn.account_id
        ):
            # txn and last_txn are a transfer
            last_txn.transfer_id = txn.id
            txn.transfer_id = last_txn.id
            session.add(txn)
            session.add(last_txn)
            logger.warning(
                'Inferred Transfer relationship between Transactions %d and %d',
                last_txn.id, txn.id
            )
            last_txn = None
            continue
        last_txn = txn
    session.commit()
    # ### end Alembic commands ###


def downgrade():
    op.drop_constraint(
        op.f(
            'fk_transactions_transfer_id_transactions'),
        'transactions',
        type_='foreignkey'
    )
    op.drop_column('transactions', 'transfer_id')
