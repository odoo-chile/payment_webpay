# -*- coding: utf-8 -*-
from openerp import SUPERUSER_ID
from openerp.osv import osv, orm, fields
from openerp.addons.web.http import request


class Website(orm.Model):
    _inherit = 'website'

    def sale_get_order(self, cr, uid, ids, force_create=False, code=None,
                       update_pricelist=None, context=None):
        """
        This function replaces the original. It was made as a countermeasure
        over a bug that happens in cases in which there are some products in
        the cart put by anonymous user, when trying to log in, an error 500
        is raised to the visitor of the website.
        This is because there is no assumed default partner_id and pricelist_id.
        In these critical instances, I am assigning partner_id as 4
        (public user), and pricelist_id = 1 (default pricelist).
        There is no effort made in order to change de class to api 8 at these
        point, and this solved the issue in most cases.
        @author: Daniel Blanco
        @date: 2017-12-04
        """
        sale_order_obj = self.pool['sale.order']
        sale_order_id = request.session.get('sale_order_id')
        sale_order = None

        # Test validity of the sale_order_id
        if sale_order_id and sale_order_obj.exists(cr, SUPERUSER_ID, sale_order_id, context=context):
            sale_order = sale_order_obj.browse(cr, SUPERUSER_ID, sale_order_id, context=context)
        else:
            sale_order_id = None

        # create so if needed
        if not sale_order_id and (force_create or code):
            # TODO cache partner_id session
            partner = self.pool['res.users'].browse(cr, SUPERUSER_ID, uid, context=context).partner_id

            for w in self.browse(cr, uid, ids):
                values = {
                    'user_id': w.user_id.id,
                    'partner_id': partner.id,
                    'pricelist_id': partner.property_product_pricelist.id,
                    'section_id': self.pool.get('ir.model.data').get_object_reference(cr, uid, 'website', 'salesteam_website_sales')[1],
                }
                sale_order_id = sale_order_obj.create(cr, SUPERUSER_ID, values, context=context)
                values = sale_order_obj.onchange_partner_id(cr, SUPERUSER_ID, [], partner.id, context=context)['value']
                sale_order_obj.write(cr, SUPERUSER_ID, [sale_order_id], values, context=context)
                request.session['sale_order_id'] = sale_order_id
                sale_order = sale_order_obj.browse(cr, SUPERUSER_ID, sale_order_id, context=context)

        if sale_order_id:
            # TODO cache partner_id session
            partner = self.pool['res.users'].browse(cr, SUPERUSER_ID, uid, context=context).partner_id
            # check for change of pricelist with a coupon
            if code and code != sale_order.pricelist_id.code:
                pricelist_ids = self.pool['product.pricelist'].search(cr, SUPERUSER_ID, [('code', '=', code)], context=context)
                if pricelist_ids:
                    pricelist_id = pricelist_ids[0]
                    request.session['sale_order_code_pricelist_id'] = pricelist_id
                    update_pricelist = True

            pricelist_id = request.session.get('sale_order_code_pricelist_id') or partner.property_product_pricelist.id

            # check for change of partner_id ie after signup
            if sale_order.partner_id.id != partner.id and request.website.partner_id.id != partner.id:
                flag_pricelist = False
                if pricelist_id != sale_order.pricelist_id.id:
                    flag_pricelist = True
                fiscal_position = sale_order.fiscal_position and sale_order.fiscal_position.id or False

                values = sale_order_obj.onchange_partner_id(cr, SUPERUSER_ID, [sale_order_id], partner.id, context=context)['value']
                if values.get('fiscal_position'):
                    order_lines = map(int,sale_order.order_line)
                    values.update(sale_order_obj.onchange_fiscal_position(cr, SUPERUSER_ID, [],
                        values['fiscal_position'], [[6, 0, order_lines]], context=context)['value'])

                values['partner_id'] = partner.id
                if not values['partner_id']:
                    values['partner_id'] = values['partner_invoice_id'] = values['partner_shipping_id'] = 4
                sale_order_obj.write(cr, SUPERUSER_ID, [sale_order_id], values, context=context)

                if flag_pricelist or values.get('fiscal_position', False) != fiscal_position:
                    update_pricelist = True

            # update the pricelist
            if update_pricelist:
                values = {'pricelist_id': pricelist_id}
                try:
                    values.update(sale_order.onchange_pricelist_id(pricelist_id, None)['value'])
                except:
                    pass
                if not pricelist_id:
                    values['pricelist_id'] = 1
                sale_order.write(values)
                for line in sale_order.order_line:
                    if line.exists():
                        sale_order._cart_update(product_id=line.product_id.id, line_id=line.id, add_qty=0)

            # update browse record
            if (code and code != sale_order.pricelist_id.code) or sale_order.partner_id.id !=  partner.id:
                sale_order = sale_order_obj.browse(cr, SUPERUSER_ID, sale_order.id, context=context)

        else:
            request.session['sale_order_id'] = None
            return None

        return sale_order
