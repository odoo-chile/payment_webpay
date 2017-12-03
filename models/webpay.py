# -*- coding: utf-'8' "-*-"

import datetime
from hashlib import sha1
import logging
import socket
from openerp import SUPERUSER_ID
from openerp import api, models, fields, _
from openerp.tools import float_round, DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.float_utils import float_compare, float_repr
from openerp.tools.safe_eval import safe_eval
from openerp.exceptions import Warning as UserError
import pytz

from base64 import b64decode

_logger = logging.getLogger(__name__)
if True:  # try:
    from suds.client import Client
    from suds.wsse import Security, Timestamp
    from .wsse.suds import WssePlugin
    from suds.transport.https import HttpTransport
else:  # except:
    _logger.info("No Load suds or wsse")

URLS ={
    'integ': 'https://webpay3gint.transbank.cl/WSWebpayTransaction/cxf/WSWebpayService?wsdl',
    'test': 'https://webpay3gint.transbank.cl/WSWebpayTransaction/cxf/WSWebpayService?wsdl',
    'prod': 'https://webpay3g.transbank.cl//WSWebpayTransaction/cxf/WSWebpayService?wsdl',
}

class PaymentAcquirerWebpay(models.Model):
    _inherit = 'payment.acquirer'

    @api.model
    def _get_providers(self,):
        providers = super(PaymentAcquirerWebpay, self)._get_providers()
        providers.append(['webpay', 'Webpay'])
        return providers

    webpay_commer_code = fields.Char(
        string="Commerce Code",)
    webpay_private_key = fields.Binary(
        string="User Private Key",)
    webpay_public_cert = fields.Binary(
        string="User Public Cert",)
    webpay_cert = fields.Binary(
        string='Webpay Cert',)
    webpay_mode = fields.Selection(
        [
            ('normal', "Normal"),
            ('mall', "Normal Mall"),
            ('oneclick', "OneClick"),
            ('completa', "Completa"),
        ],
        string="Webpay Mode",
        )
    environment = fields.Selection(
        selection_add=[('integ', 'Integración')],
        )

    @api.multi
    def _get_feature_support(self):
        res = super(PaymentAcquirerWebpay, self)._get_feature_support()
        res['fees'].append('webpay')
        return res

    def _get_webpay_urls(self):
        url = URLS[self.environment]
        return url

    @api.multi
    def webpay_form_generate_values(self, partner_values, tx_values):
        # raise UserError(partner_values)
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url')
        tx_values.update({
            'business': self.company_id.name,
            'item_name': '%s: %s' % (
                self.company_id.name, tx_values['reference']),
            'item_number': tx_values['reference'],
            'amount': tx_values['amount'],
            'currency_code': tx_values['currency'] and tx_values[
                'currency'].name or '',
            'address1': partner_values.get('address'),
            'city': partner_values.get('city'),
            'country': partner_values.get('country') and partner_values.get(
                'country').code or '',
            'state': partner_values.get('state') and (
                partner_values.get('state').code or partner_values.get(
                    'state').name) or '',
            'email': partner_values.get('email'),
            'zip_code': partner_values.get('zip'),
            'first_name': partner_values.get('first_name'),
            'last_name': partner_values.get('last_name'),
            'return_url': base_url + '/payment/webpay/final',
        })
        return partner_values, tx_values

    @api.multi
    def webpay_get_form_action_url(self,):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return base_url +'/payment/webpay/redirect'

    def get_private_key(self):
        return b64decode(self.webpay_private_key)

    def get_public_cert(self):
        return b64decode(self.webpay_public_cert)

    def get_WebPay_cert(self):
        return b64decode(self.webpay_cert)

    def get_client(self,):
        transport=HttpTransport()
        wsse = Security()

        return Client(
            self._get_webpay_urls(),
            transport=transport,
            wsse=wsse,
            plugins=[
                WssePlugin(
                    keyfile=self.get_private_key(),
                    certfile=self.get_public_cert(),
                    their_certfile=self.get_WebPay_cert(),
                ),
            ],
        )

    """
    initTransaction

    Permite inicializar una transaccion en Webpay.
    Como respuesta a la invocacion se genera un token que representa en forma unica una transaccion.
    """
    def initTransaction(self, post):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        client = self.get_client()
        client.options.cache.clear()
        init = client.factory.create('wsInitTransactionInput')

        init.wSTransactionType = client.factory.create('wsTransactionType').TR_NORMAL_WS

        init.commerceId = self.webpay_commer_code

        init.buyOrder = post['item_number']
        init.sessionId = self.company_id.id
        init.returnURL = base_url + '/payment/webpay/return/'+str(self.id)
        init.finalURL =  post['return_url']

        detail = client.factory.create('wsTransactionDetail')
        detail.amount = post['amount']

        detail.commerceCode = self.webpay_commer_code
        detail.buyOrder = post['item_number']

        init.transactionDetails.append(detail)
        init.wPMDetail=client.factory.create('wpmDetailInput')

        wsInitTransactionOutput = client.service.initTransaction(init)

        return wsInitTransactionOutput


class PaymentTxWebpay(models.Model):
    _inherit = 'payment.transaction'

    webpay_txn_type = fields.Selection([
            ('VD','Débito'),
            ('VN','Crédito sin cuotas'),
            ('VC','Crédito en cuotas'),
            ('SI','Crédito, 3 cuotas sin interés'),
            ('S2','Crédito, cuotas sin interés'),
            ('NC','Crédito, Cuotas sin interés'),
        ],
       string="Webpay Tipo Transacción")
    card_detail = fields.Char("Card Detail")
    shares_amount = fields.Float("Shares Amount")
    shares_number = fields.Integer("Qty of Shares")
    vci = fields.Selection([
        ('TSY', 'Autenticación exitosa'), ('TSN', 'Autenticación fallida'),
        ('TO6', 'Tiempo máximo excedido para autenticación'),
        ('ABO', 'Autenticación abortada por tarjetahabiente'),
        ('U3', 'Error interno en la autenticación'),
        ('', 'N/A')], default='', string="VCI")

    """
    getTransaction

    Permite obtener el resultado de la transaccion una vez que
    Webpay ha resuelto su autorizacion financiera.
    """
    @api.multi
    def getTransaction(self, acquirer_id, token):
        client = acquirer_id.get_client()
        client.options.cache.clear()
        transactionResultOutput = client.service.getTransactionResult(token)
        acknowledge = self.acknowledgeTransaction(acquirer_id, token)

        return transactionResultOutput


    """
    acknowledgeTransaction
    Indica  a Webpay que se ha recibido conforme el resultado de la transaccion
    """
    def acknowledgeTransaction(self, acquirer_id, token):
        client = acquirer_id.get_client()
        client.options.cache.clear()
        acknowledge = client.service.acknowledgeTransaction(token)
        return acknowledge

    def _webpay_form_get_tx_from_data(self, cr, uid, data, context=None):
        reference, txn_id = data.buyOrder, data.sessionId
        if not reference or not txn_id:
            error_msg = _('Webpay: received data with missing reference (%s) or txn_id (%s)') % (reference, txn_id)
            _logger.info(error_msg)
            raise ValidationError(error_msg)

        # find tx -> @TDENOTE use txn_id ?
        tx_ids = self.pool['payment.transaction'].search(cr, uid, [('reference', '=', reference)], context=context)
        if not tx_ids or len(tx_ids) > 1:
            error_msg = 'Webpay: received data for reference %s' % (reference)
            if not tx_ids:
                error_msg += '; no order found'
            else:
                error_msg += '; multiple order found'
            _logger.warning(error_msg)
            raise ValidationError(error_msg)
        return self.browse(cr, uid, tx_ids[0], context=context)

    def _webpay_form_validate(self, cr, uid, tx, data, context=None):
        codes = {
                '0' : 'Transacción aprobada.',
                '-1' : 'Rechazo de transacción.',
                '-2' : 'Transacción debe reintentarse.',
                '-3' : 'Error en transacción.',
                '-4' : 'Rechazo de transacción.',
                '-5' : 'Rechazo por error de tasa.',
                '-6' : 'Excede cupo máximo mensual.',
                '-7' : 'Excede límite diario por transacción.',
                '-8' : 'Rubro no autorizado.',
            }
        status = str(data.detailOutput[0].responseCode)
        _logger.info('#####..--info--..##### %s' % status)
        # utctime = pytz.timezone('Etc/GMT+3')
        # date_time = data.transactionDate.replace(tzinfo=utctime)
        # date_time = utctime.normalize(date_time)
        date_time = (data.transactionDate + datetime.timedelta(0, 10800)).strftime("%Y-%m-%d %H:%M:%S")
        _logger.info('··········########### DATETIME %s' % date_time)
        res = {
            'acquirer_reference': data.detailOutput[0].authorizationCode,
            'webpay_txn_type': data.detailOutput[0].paymentTypeCode,
            'card_detail': data.cardDetail['cardNumber'],
        }
        try:
            res.update(vci=data.VCI)
        except AttributeError:
            _logger.info('VCI no informado')
        if status in ['0']:
            _logger.info('Validated webpay payment for tx %s: set as done' % (tx.reference))
            res.update(state='done', date_validate=date_time)
            try:
                res.update(shares_amount=data.detailOutput[0].sharesAmount,
                           shares_number=data.detailOutput[0].sharesNumber)
            except AttributeError:
                res.update(shares_amount=0, shares_number=0)
            return tx.write(res)
        elif status in ['-6', '-7']:
            _logger.info('Received notification for webpay payment %s: set as pending' % (tx.reference))
            res.update(state='pending', state_message=data.get('pending_reason', ''))
            return tx.write(res)
        else:
            error = 'Received unrecognized status for webpay payment %s: %s, set as error' % (tx.reference, codes[status].decode('utf-8'))
            _logger.warning(error)
            res.update(state='error', state_message=error)
            return tx.write(res)


'''
class PaymentMethod(models.Model):
    _inherit = 'payment.method'
'''
