function validate_email(email, pname){
    var current_user = $('input:hidden[name=current_user]').val();
    console.log('usuario actual:' +current_user);
    console.log('validador de email unico:'+email)
    openerp.jsonRpc('/email/unique', 'call', {'email': email, 'formpartner': pname})
        .then(function(result) {
            console.log(result);
            if (result!='OK'){
                console.log('email repetido')
                $('#alert3').show();
                $('#sendit').attr('disabled', true);
                $("input[name='email']")
                    .closest("div")
                    .addClass("has-error");
                /*$("input[name='email']")
                    .focus();*/
                return false;
            }
            else{
                console.log('email ok');
                $('#alert3').hide();
                $('#sendit').attr('disabled', false);
                $("input[name='email']")
                    .closest("div")
                    .removeClass("has-error");
                /*$("input[name='email']")
                    .focus();*/
                return true;
            }
        }
    );
}
function validate_rut(pvat){
    console.log('validador de rut: '+pvat);
    openerp.jsonRpc('/vat/valid', 'call', {'formatted_vat': pvat})
        .then(function(result) {
            console.log(result);
            if (result==false){
                console.log('rut invalido');
                $('#alert1').show();
                $('#alert2').hide();
                $('#alert3').hide();
                $('#sendit').attr('disabled', true);
                $( 'input:text[name=no_country_field]' )
                  .closest( "div" )
                  .addClass( "has-error" );
                /*$( 'input:text[name=vat]' )
                  .focus();*/
                return false;
            }
            else{
                console.log('rut valido');
                $('#alert1').hide();
                $('input:hidden[name=vat]').val(result)
                pvat = result
                var pname = $('input:text[name=name]').val()
                console.log('cambio de rut: '+pvat);
                console.log('partner: '+pname);
                openerp.jsonRpc('/vat/unique', 'call', {'formatted_vat': pvat, 'formpartner': pname})
                    .then(function(result) {
                        console.log(result);
                        if ( result!='OK'){
                            if(result!=pname){
                              console.log('rut repetido');
                              $('#alert1').hide();
                              $('#alert2').show();
                              $('#sendit').attr('disabled', true);
                              $('input:text[name=no_country_field]')
                                  .closest( "div" )
                                  .addClass( "has-error" );
                              /*$('input:text[name=no_country_field]')
                                .focus();*/
                              return false;
                            }
                            else{
                              console.log('rut de la misma empresa');
                              $('#alert1').hide();
                              $('#alert2').hide();
                              $('#alert3').hide();
                              $('#sendit').attr('disabled', false);
                              $('input:text[name=no_country_field]')
                                .closest( "div" )
                                .removeClass( "has-error" );
                              /*$('input:text[name=no_country_field]')
                                .focus();*/
                              return true;
                            }
                        }
                        else{
                            console.log('rut ok');
                            $('#alert1').hide();
                            $('#alert2').hide();
                            $('#alert3').hide();
                            $('#sendit').attr('disabled', false);
                            $('input:text[name=no_country_field]')
                                .closest( "div" )
                                .removeClass( "has-error" );
                            return true;
                        }
                    }
                );
            }
        }
    );
}

$('#is_company').change(function(){
    console.log($('#is_company').attr('checked'));
    if($('#is_company').attr('checked')){
        $('input:text[name=name]').attr('placeholder', 'Ingrese nombre de la empresa');
    }
    else{
        $('input:text[name=name]').attr('placeholder', 'Ingrese su nombre y apellido');
    }
});

$('input:text[name=no_country_field]').blur(function(){
    var pvat = $('input:hidden[name=vat]').val();
    validate_rut(pvat);
});

$("input[name='email']").blur(function(){
    var email = $("input[name='email']").val();
    var pname = $('input:text[name=name]').val();
    validate_email(email, pname);
});


/*
$('#sendit').click(function(){
    console.log('entra a sendit');
    var pvat = $('input:hidden[name=vat]').val();
    console.log('rut' + pvat);
    if (validate_rut(pvat)) {
        console.log('valida rut');
        $("#checkout_form").submit();
        console.log('despues de submit');
    }
    else{
        console.log('no valida rut');
    }
});
*/

$(document).ready(function(){
    $('#btn_vat_code').prop('disabled', true);
    /*$('#no_country_field').prop('placeholder', 'Si es extranjero, utilice RUT 66.666.666-6');*/
    $("#no_country_field").prop('placeholder', 'Extranjero: 66.666.666-6');
    $('#no_country_field').focus();
    //$('#sendit').prop('disabled', true);
    $('#sendit').attr('disabled', true);
    var pvat = $('input:text[name=vat]').val();
    validate_rut(pvat);
});
$("#no_country_field").mouseover(function(){
    $("#no_country_field").attr('title', 'Extranjero: 66.666.666-6');
});

