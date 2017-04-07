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

import pytest
from datetime import timedelta, date
from selenium.webdriver.support.ui import Select

from biweeklybudget.utils import dtnow
from biweeklybudget.tests.acceptance_helpers import AcceptanceHelper
from biweeklybudget.models.transaction import Transaction


@pytest.mark.acceptance
class TestTransactions(AcceptanceHelper):

    @pytest.fixture(autouse=True)
    def get_page(self, base_url, selenium, testflask, refreshdb):  # noqa
        self.baseurl = base_url
        selenium.get(base_url + '/transactions')

    def test_heading(self, selenium):
        heading = selenium.find_element_by_class_name('navbar-brand')
        assert heading.text == 'Transactions - BiweeklyBudget'

    def test_nav_menu(self, selenium):
        ul = selenium.find_element_by_id('side-menu')
        assert ul is not None
        assert 'nav' in ul.get_attribute('class')
        assert ul.tag_name == 'ul'

    def test_notifications(self, selenium):
        div = selenium.find_element_by_id('notifications-row')
        assert div is not None
        assert div.get_attribute('class') == 'row'


@pytest.mark.acceptance
class TestTransactionsDefault(AcceptanceHelper):

    @pytest.fixture(autouse=True)
    def get_page(self, base_url, selenium, testflask, refreshdb):  # noqa
        self.baseurl = base_url
        self.dt = dtnow()
        selenium.get(base_url + '/transactions')

    def test_table(self, selenium):
        table = selenium.find_element_by_id('table-transactions')
        texts = self.tbody2textlist(table)
        elems = self.tbody2elemlist(table)
        assert texts == [
            [
                (self.dt + timedelta(days=4)).date().strftime('%Y-%m-%d'),
                '$111.13',
                'T1foo',
                'BankOne (1)',
                'Periodic1 (1)',
                'Yes (1)',
                '$111.11'
            ],
            [
                self.dt.date().strftime('%Y-%m-%d'),
                '$-333.33',
                'T2',
                'BankTwoStale (2)',
                'Standing1 (4)',
                'Yes (3)',
                ''
            ],
            [
                (self.dt - timedelta(days=2)).date().strftime('%Y-%m-%d'),
                '$222.22',
                'T3',
                'CreditOne (3)',
                'Periodic2 (2)',
                '',
                ''
            ]
        ]
        linkcols = [
            [
                c[2].get_attribute('innerHTML'),
                c[3].get_attribute('innerHTML'),
                c[4].get_attribute('innerHTML'),
                c[5].get_attribute('innerHTML')
            ]
            for c in elems
        ]
        assert linkcols[0] == [
            '<a href="javascript:transModal(1, mytable)">T1foo</a>',
            '<a href="/accounts/1">BankOne (1)</a>',
            '<a href="/budgets/1">Periodic1 (1)</a>',
            '<a href="/scheduled/1">Yes (1)</a>'
        ]
        assert linkcols[1] == [
            '<a href="javascript:transModal(2, mytable)">T2</a>',
            '<a href="/accounts/2">BankTwoStale (2)</a>',
            '<a href="/budgets/4">Standing1 (4)</a>',
            '<a href="/scheduled/3">Yes (3)</a>'
        ]
        assert linkcols[2] == [
            '<a href="javascript:transModal(3, mytable)">T3</a>',
            '<a href="/accounts/3">CreditOne (3)</a>',
            '<a href="/budgets/2">Periodic2 (2)</a>',
            '&nbsp;'
        ]

    def test_filter_opts(self, selenium):
        selenium.get(self.baseurl + '/transactions')
        acct_filter = Select(selenium.find_element_by_id('account_filter'))
        # find the options
        opts = []
        for o in acct_filter.options:
            opts.append([o.get_attribute('value'), o.text])
        assert opts == [
            ['None', ''],
            ['1', 'BankOne'],
            ['2', 'BankTwoStale'],
            ['3', 'CreditOne'],
            ['4', 'CreditTwo'],
            ['6', 'DisabledBank'],
            ['5', 'InvestmentOne']
        ]

    def test_filter(self, selenium):
        p1trans = [
            'T1foo',
            'T2',
            'T3'
        ]
        selenium.get(self.baseurl + '/transactions')
        table = self.retry_stale(
            selenium.find_element_by_id,
            'table-transactions'
        )
        texts = self.retry_stale(self.tbody2textlist, table)
        trans = [t[2] for t in texts]
        # check sanity
        assert trans == p1trans
        acct_filter = Select(selenium.find_element_by_id('account_filter'))
        # select Monthly
        acct_filter.select_by_value('1')
        table = self.retry_stale(
            selenium.find_element_by_id,
            'table-transactions'
        )
        texts = self.retry_stale(self.tbody2textlist, table)
        trans = [t[2] for t in texts]
        assert trans == ['T1foo']
        # select back to all
        acct_filter.select_by_value('None')
        table = self.retry_stale(
            selenium.find_element_by_id,
            'table-transactions'
        )
        texts = self.retry_stale(self.tbody2textlist, table)
        trans = [t[2] for t in texts]
        assert trans == p1trans

    def test_search(self, selenium):
        selenium.get(self.baseurl + '/transactions')
        search = self.retry_stale(
            selenium.find_element_by_xpath,
            '//input[@type="search"]'
        )
        search.send_keys('foo')
        self.wait_for_jquery_done(selenium)
        table = self.retry_stale(
            selenium.find_element_by_id,
            'table-transactions'
        )
        texts = self.retry_stale(self.tbody2textlist, table)
        trans = [t[2] for t in texts]
        # check sanity
        assert trans == ['T1foo']


@pytest.mark.acceptance
@pytest.mark.usefixtures('class_refresh_db', 'refreshdb', 'testflask')
class TestTransModal(AcceptanceHelper):

    def test_0_verify_db(self, testdb):
        t = testdb.query(Transaction).get(1)
        assert t is not None
        assert t.description == 'T1foo'
        assert t.date == (dtnow() + timedelta(days=4)).date()
        assert float(t.actual_amount) == 111.13
        assert float(t.budgeted_amount) == 111.11
        assert t.account_id == 1
        assert t.budget_id == 1
        assert t.scheduled_trans_id == 1
        assert t.notes == 'notesT1'

    def test_1_modal_on_click(self, base_url, selenium):
        self.baseurl = base_url
        selenium.get(base_url + '/transactions')
        link = selenium.find_element_by_xpath('//a[text()="T1foo"]')
        link.click()
        modal, title, body = self.get_modal_parts(selenium)
        self.assert_modal_displayed(modal, title, body)
        assert title.text == 'Edit Transaction 1'
        assert body.find_element_by_id(
            'trans_frm_id').get_attribute('value') == '1'
        assert body.find_element_by_id(
            'trans_frm_date').get_attribute('value') == (
            dtnow() + timedelta(days=4)).date().strftime('%Y-%m-%d')
        assert body.find_element_by_id(
            'trans_frm_amount').get_attribute('value') == '111.13'
        assert body.find_element_by_id(
            'trans_frm_description').get_attribute('value') == 'T1foo'
        acct_sel = Select(body.find_element_by_id('trans_frm_account'))
        opts = []
        for o in acct_sel.options:
            opts.append([o.get_attribute('value'), o.text])
        assert opts == [
            ['None', ''],
            ['1', 'BankOne'],
            ['2', 'BankTwoStale'],
            ['3', 'CreditOne'],
            ['4', 'CreditTwo'],
            ['6', 'DisabledBank'],
            ['5', 'InvestmentOne']
        ]
        assert acct_sel.first_selected_option.get_attribute('value') == '1'
        budget_sel = Select(body.find_element_by_id('trans_frm_budget'))
        opts = []
        for o in budget_sel.options:
            opts.append([o.get_attribute('value'), o.text])
        assert opts == [
            ['None', ''],
            ['7', 'Income (income)'],
            ['1', 'Periodic1'],
            ['2', 'Periodic2'],
            ['3', 'Periodic3 Inactive'],
            ['4', 'Standing1'],
            ['5', 'Standing2'],
            ['6', 'Standing3 Inactive']
        ]
        assert budget_sel.first_selected_option.get_attribute('value') == '1'
        assert selenium.find_element_by_id(
            'trans_frm_notes').get_attribute('value') == 'notesT1'

    def test_2_modal_edit(self, base_url, selenium):
        self.baseurl = base_url
        selenium.get(base_url + '/transactions')
        link = selenium.find_element_by_xpath('//a[text()="T1foo"]')
        link.click()
        modal, title, body = self.get_modal_parts(selenium)
        self.assert_modal_displayed(modal, title, body)
        assert title.text == 'Edit Transaction 1'
        assert body.find_element_by_id(
            'trans_frm_id').get_attribute('value') == '1'
        d = body.find_element_by_id('trans_frm_date')
        d.clear()
        d.send_keys(
            (dtnow() - timedelta(days=3)).date().strftime('%Y-%m-%d')
        )
        amt = body.find_element_by_id('trans_frm_amount')
        amt.clear()
        amt.send_keys('-123.45')
        desc = body.find_element_by_id('trans_frm_description')
        desc.send_keys('edited')
        acct_sel = Select(body.find_element_by_id('trans_frm_account'))
        acct_sel.select_by_value('4')
        budget_sel = Select(body.find_element_by_id('trans_frm_budget'))
        budget_sel.select_by_value('5')
        notes = selenium.find_element_by_id('trans_frm_notes')
        notes.send_keys('edited')
        # submit the form
        selenium.find_element_by_id('modalSaveButton').click()
        self.wait_for_jquery_done(selenium)
        # check that we got positive confirmation
        _, _, body = self.get_modal_parts(selenium)
        x = body.find_elements_by_tag_name('div')[0]
        assert 'alert-success' in x.get_attribute('class')
        assert x.text.strip() == 'Successfully saved Transaction 1 ' \
                                 'in database.'
        # dismiss the modal
        selenium.find_element_by_id('modalCloseButton').click()
        self.wait_for_jquery_done(selenium)
        # test that updated budget was removed from the page
        table = selenium.find_element_by_id('table-transactions')
        texts = [y[2] for y in self.tbody2textlist(table)]
        assert 'T1fooedited' in texts

    def test_3_verify_db(self, testdb):
        t = testdb.query(Transaction).get(1)
        assert t is not None
        assert t.description == 'T1fooedited'
        assert t.date == (dtnow() - timedelta(days=3)).date()
        assert float(t.actual_amount) == -123.45
        assert float(t.budgeted_amount) == 111.11
        assert t.account_id == 4
        assert t.budget_id == 5
        assert t.scheduled_trans_id == 1
        assert t.notes == 'notesT1edited'


@pytest.mark.acceptance
@pytest.mark.usefixtures('class_refresh_db', 'refreshdb', 'testflask')
class TestTransModalByURL(AcceptanceHelper):

    def test_0_verify_db(self, testdb):
        t = testdb.query(Transaction).get(3)
        assert t is not None
        assert t.description == 'T3'
        assert t.date == (dtnow() - timedelta(days=2)).date()
        assert float(t.actual_amount) == 222.22
        assert t.budgeted_amount is None
        assert t.account_id == 3
        assert t.budget_id == 2
        assert t.scheduled_trans_id is None
        assert t.notes == 'notesT3'

    def test_1_modal(self, base_url, selenium):
        self.baseurl = base_url
        selenium.get(base_url + '/transactions/3')
        modal, title, body = self.get_modal_parts(selenium)
        self.assert_modal_displayed(modal, title, body)
        assert title.text == 'Edit Transaction 3'
        assert body.find_element_by_id(
            'trans_frm_id').get_attribute('value') == '3'
        assert body.find_element_by_id(
            'trans_frm_date').get_attribute('value') == (
            dtnow() - timedelta(days=2)).date().strftime('%Y-%m-%d')
        assert body.find_element_by_id(
            'trans_frm_amount').get_attribute('value') == '222.22'
        assert body.find_element_by_id(
            'trans_frm_description').get_attribute('value') == 'T3'
        acct_sel = Select(body.find_element_by_id('trans_frm_account'))
        opts = []
        for o in acct_sel.options:
            opts.append([o.get_attribute('value'), o.text])
        assert opts == [
            ['None', ''],
            ['1', 'BankOne'],
            ['2', 'BankTwoStale'],
            ['3', 'CreditOne'],
            ['4', 'CreditTwo'],
            ['6', 'DisabledBank'],
            ['5', 'InvestmentOne']
        ]
        assert acct_sel.first_selected_option.get_attribute('value') == '3'
        budget_sel = Select(body.find_element_by_id('trans_frm_budget'))
        opts = []
        for o in budget_sel.options:
            opts.append([o.get_attribute('value'), o.text])
        assert opts == [
            ['None', ''],
            ['7', 'Income (income)'],
            ['1', 'Periodic1'],
            ['2', 'Periodic2'],
            ['3', 'Periodic3 Inactive'],
            ['4', 'Standing1'],
            ['5', 'Standing2'],
            ['6', 'Standing3 Inactive']
        ]
        assert budget_sel.first_selected_option.get_attribute('value') == '2'
        assert selenium.find_element_by_id(
            'trans_frm_notes').get_attribute('value') == 'notesT3'


@pytest.mark.acceptance
@pytest.mark.usefixtures('class_refresh_db', 'refreshdb', 'testflask')
class TestTransAddModal(AcceptanceHelper):

    def test_2_modal_add(self, base_url, selenium):
        self.baseurl = base_url
        selenium.get(base_url + '/transactions')
        link = selenium.find_element_by_id('btn_add_trans')
        link.click()
        modal, title, body = self.get_modal_parts(selenium)
        self.assert_modal_displayed(modal, title, body)
        assert title.text == 'Add New Transaction'
        date_input = body.find_element_by_id('trans_frm_date')
        # BEGIN select the 15th of this month from the popup
        dnow = dtnow()
        expected_date = date(year=dnow.year, month=dnow.month, day=15)
        date_input.click()
        date_number = body.find_element_by_xpath(
            '//td[@class="day" and text()="15"]'
        )
        date_number.click()
        assert date_input.get_attribute(
            'value') == expected_date.strftime('%Y-%m-%d')
        # END date chooser popup
        amt = body.find_element_by_id('trans_frm_amount')
        amt.clear()
        amt.send_keys('123.45')
        desc = body.find_element_by_id('trans_frm_description')
        desc.send_keys('NewTrans4')
        acct_sel = Select(body.find_element_by_id('trans_frm_account'))
        acct_sel.select_by_value('1')
        budget_sel = Select(body.find_element_by_id('trans_frm_budget'))
        budget_sel.select_by_value('2')
        notes = selenium.find_element_by_id('trans_frm_notes')
        notes.send_keys('NewTransNotes')
        # submit the form
        selenium.find_element_by_id('modalSaveButton').click()
        self.wait_for_jquery_done(selenium)
        # check that we got positive confirmation
        _, _, body = self.get_modal_parts(selenium)
        x = body.find_elements_by_tag_name('div')[0]
        assert 'alert-success' in x.get_attribute('class')
        assert x.text.strip() == 'Successfully saved Transaction 4 ' \
                                 'in database.'
        # dismiss the modal
        selenium.find_element_by_id('modalCloseButton').click()
        self.wait_for_jquery_done(selenium)
        # test that new trans was added to the table
        table = selenium.find_element_by_id('table-transactions')
        texts = [y[2] for y in self.tbody2textlist(table)]
        assert 'NewTrans4' in texts

    def test_3_verify_db(self, testdb):
        t = testdb.query(Transaction).get(4)
        assert t is not None
        assert t.description == 'NewTrans4'
        dnow = dtnow()
        assert t.date == date(year=dnow.year, month=dnow.month, day=15)
        assert float(t.actual_amount) == 123.45
        assert t.budgeted_amount is None
        assert t.account_id == 1
        assert t.budget_id == 2
        assert t.scheduled_trans_id is None
        assert t.notes == 'NewTransNotes'