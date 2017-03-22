"""
The latest version of this package is available at:
<http://github.com/jantman/biweeklybudget>

################################################################################
Copyright 2016 Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>

    This file is part of biweeklybudget, also known as biweeklybudget.

    biweeklybudget is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    biweeklybudget is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with biweeklybudget.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/biweeklybudget> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################
"""

from flask.views import MethodView
from flask import render_template

from biweeklybudget.flaskapp.app import app
from biweeklybudget.flaskapp.controllers.notifications import (
    NotificationsController
)
from biweeklybudget.models.account import Account, AcctType
from biweeklybudget.db import db_session


class IndexView(MethodView):

    def get(self):
        return render_template(
            'index.html',
            bank_accounts=db_session.query(Account).filter(
                Account.acct_type == AcctType.Bank,
                Account.is_active == True).all(),  # noqa
            credit_accounts=db_session.query(Account).filter(
                Account.acct_type == AcctType.Credit,
                Account.is_active == True).all(),  # noqa
            investment_accounts=db_session.query(Account).filter(
                Account.acct_type == AcctType.Investment,
                Account.is_active == True).all(),  # noqa
            notifications=NotificationsController().get_notifications()
        )

app.add_url_rule('/', view_func=IndexView.as_view('index_view'))