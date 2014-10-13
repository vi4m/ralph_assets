/*jshint multistr: true */
(function(){
    "use strict";

    var Report = function () {};
    var Bulk = function () {};
    var TableListing = function () {};

    function collapse_all_children(parent_uid) {
            var children = $('[data-parent='+parent_uid+']');
            while(children !== undefined && children.length){
                children.css('display', 'none');
                var uid = $(children[0]).data('uid')
                children = $('[data-parent='+uid+']');
            }
            return true;
        }
    var expand_children = function(parent_uid) {
            var children = $('[data-parent='+parent_uid+']');
            if (children !== undefined && children.length){
                children.css('display', 'table-row');
                children.removeClass('hide');
            }
        }

    Report.prototype.prepare = function() {
        $('.report').find('tr')
            .click(function(event) {
                if(event.target == $('span', this)[0] || event.target == $('.icon', this)[0])
                {
                    var uid = $(this).data('uid');
                    if($(this).hasClass('root') || $(this).hasClass('collapsed')){
                        $(this).addClass('expanded').removeClass('collapsed').removeClass('root');
                        expand_children(uid);
                    }
                    else
                    {
                        $(this).removeClass('expanded').addClass('collapsed');
                        collapse_all_children(uid);
                    }
                }
            })
    };

    Report.prototype.expand_all = function() {
        $('.report').find('tr')
            .css('display', 'table-row')
            .removeClass('collapsed')
            .addClass('expanded');
    };

    Report.prototype.collapse_all = function() {
        $('.report').find('tr')
            .css('display', 'none')
            .removeClass('expanded')
            .addClass('collapsed');
        $('.level-1').css('display', 'table-row');
        $('thead tr').css('display', 'table-row');
    };

    TableListing.prototype.toggleChildDisplay = function(){
        var trigger = this;
        var trgt_id = $(trigger).attr('data-trgt');
        if (trgt_id.length === 0) {
            throw {
                'name': "TargetNotSpecified",
                'description': "Attribute 'data-trgt' not specified.",
            };
        }
        var threshold = $(trigger).attr('data-threshold') || 5;
        var targets = $('#' + trgt_id).children().slice(threshold);
        $(targets).each(function(idx, trgt) {
            $(trgt).toggle();
        });

        // swap button text msg
        var currentMsg = $(trigger).text();
        var altMsg = $(trigger).attr('data-alt-msg');
        $(trigger).attr('data-alt-msg', currentMsg);
        $(trigger).text(altMsg);
    };

    Bulk.prototype.get_ids = function(){
        var ids = [];
        $("#assets_table input[type=checkbox]").each(
            function(index, val){
                if(val.checked) {
                    ids.push($(val).val());
                }
            }
        );
        return ids;
    };

    Bulk.prototype.action_selected = function(action) {
        var ids = this.get_ids();
        var selected_all_pages = $('.selected-assets-info-box').data('selected');
        if (selected_all_pages) {
            var search = window.location.search;
            search += search ? "&" : "?";
            window.location.href = action + search + 'from_query=1';
        } else if (ids.length) {
            window.location.href = action + '?select=' + ids.join('&select=');
        }
        return false;
    };

    Bulk.prototype.edit_selected = function() {
        return this.action_selected('bulkedit');
    };

    Bulk.prototype.invoice_report_selected = function() {
        return this.action_selected('invoice_report');
    };

    Bulk.prototype.addAttachment = function(type) {
        var ids = this.get_ids();
        if (ids.length){
            window.location.href = 'add_attachment/' + type + '/?select=' + ids.join('&select=');
        }
    };

    Bulk.prototype.transition_selected = function(type) {
        var ids = this.get_ids();
        var params = window.location.search;
        var selected_all_pages = $('.selected-assets-info-box').data('selected');

        if (selected_all_pages &&
            params.length &&
            $.inArray(type, ['release-asset', 'return-asset', 'loan-asset', 'change-hostname']) != -1
        ) {
             window.location.href = 'transition' + params + '&from_query=1&transition_type=' + type;
        } else if (
            ids.length &&
            $.inArray(type, ['release-asset', 'return-asset', 'loan-asset', 'change-hostname']) != -1
        ) {
            window.location.href = 'transition?select=' + ids.join('&select=') + '&transition_type=' + type;
        }
    };

    Bulk.prototype.append_bob_select_item = function() {
        // append item to select on all pages
        if ($('[data-searched-items]').data('searched-items') && $('.pagination li').length > 1 ){
            var item = $('.select-all-pages');
            var new_item = item.clone();
            item.remove();
            $('#assets_table .dropdown .dropdown-menu'  ).prepend(new_item);
            new_item.show();
        }
    };

    Bulk.prototype.select_all_pages = function() {
        var selected_box = $('.selected-assets-info-box');
        var selected_all_pages = selected_box.data('selected');
        $('.bob-select-all-pages i').toggleClass('fugue-blue-documents-stack fugue-documents-stack');
        $('.bob-select-all-pages span').toggle();
        $(selected_box).toggle();
        selected_all_pages = !selected_all_pages;
        selected_box.data('selected', selected_all_pages);
        var table = $('#assets_table');
        if (selected_all_pages){
            table.find('input[name="select"]').prop('checked', true);
            table.find('input[name="items"]').prop('checked', true);
        } else {
            table.find('input[name="select"]').prop('checked', false);
            table.find('input[name="items"]').prop('checked', false);
            table.find('input[name="selectall"]').prop('checked', false);
        }
    };


    $(document).ready(function() {
        var report = new Report();
        var bulk = new Bulk();
        var tableListing = new TableListing();

        report.prepare();

        $('.ajax.summary').click(function(){
            $.get($(this).attr('href'), function(data){
                $('.alert.summary').remove();
                $('.alert.alert-info').parent().prepend(
                    '<div class="alert alert-success summary">'+
                        data.total + ' licences in total.<br/>' +
                        data.used_by_users + ' licences assigned to users.<br/>' +
                        data.used_by_assets + ' licences assigned to assets.' +
                    '</div>'
                );
                window.scrollTo(0,0);
            })
            return false;
        });

        $('.report .expand-all').click(function(){
            report.expand_all();
        });
        $('.report .collapse-all').click(function(){
            report.collapse_all();
        });

        $('#post_edit_all').click(function() {
            bulk.edit_selected();
        });

        $('.bob-select-all, .bob-select-toggle, .bob-select-none').click(function() {
            $('.selected-assets-info-box').hide();
            $('.selected-assets-info-box').data('selected', false);
        });

        $('#post_invoice_report_selected').click(function() {
            bulk.invoice_report_selected();
        });
        $('#post_invoice_report_search_query').click(function() {
            bulk.invoice_report_search_query();
        });

        $(" #post_release_transition_selected, \
            #post_return_transition_selected, \
            #post_loan_transition_selected \
        ").click(function() {
            var type = $(this).data('transition-type');
            bulk.transition_selected(type);
        });

        $('#post_add_attachment').click(function() {
            bulk.addAttachment('asset');
        });

        $('.delete-attachment').click(function() {
            if (!confirm("Are you sure to delete Attachment(s)?")) {
                return false;
            }
            var delete_type = $(this).attr('data-delete-type');
            var form_id = '#' + $(this).attr('data-form-id');
            $(form_id).find("input[name='delete_type']").val(delete_type);
            $(form_id).submit();
        });

        $('.del-asset-btn').click(function() {
            if (!confirm("Are you sure to delete Asset?")) {
                return false;
            }
        });
        require(['reports'], function(reports) {
            reports.setup({
                trigger: $('.pagination').find('a').last(),
                progressBar: '#async-progress',
                etaEl: '#eta'
            });
        });

        require(['reports'], function(reports) {
            reports.setup({
                trigger: $('[data-role="async-report"]'),
                progressBar: '#async-progress',
                etaEl: '#eta'
            });
        });

        bulk.append_bob_select_item();

        $('.bob-select-all-pages').click(function() {
            bulk.select_all_pages();
        });

        // set status as 'in progress' if user is selected
        $("div.user_info #id_user").add('.bulk-table [id$="-user"]').change(function() {
            var $this = $(this);
            if($this.val() !== "") {
                var prefix = $this.attr('id').slice(0, -"user".length);
                var slave = $('#' + prefix + "status");
                slave.children('option').filter(function () {
                    return $(this).text() == 'in progress';
                }).prop('selected', true);
            }
        });

        $('.toggle-child-display').click(tableListing.toggleChildDisplay);

        var detectedChanges = false;

        $('.detect-changes :input').not('[type=hidden]').change(function(){
            detectedChanges = true;
        })

        $('.detect-changes [type=submit]').click(function(){
            detectedChanges = false;
        })

        window.onbeforeunload = function(e) {
            if(detectedChanges)
                return 'Detected unsaved changes on form.';
        }
    });

})();
