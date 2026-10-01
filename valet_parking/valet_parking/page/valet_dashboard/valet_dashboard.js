// Copyright (c) 2026, Valet Parking Team and contributors
// For license information, please see license.txt

frappe.pages['valet-dashboard'].on_page_load = function(wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: __('Valet Dashboard'),
        single_column: true
    });

    page.valet_dashboard = new ValetDashboard(page);
};

class ValetDashboard {
    constructor(page) {
        this.page = page;
        this.container = $(page.body);
        this.search_query = "";

        this.setup_actions();
        this.setup_layout();
        this.refresh();
    }

    setup_actions() {
        this.page.set_primary_action(__('New Ticket'), () => {
            frappe.new_doc('Parking Ticket', {}, (doc) => {
                this.refresh();
            });
        }, 'add');

        this.page.add_menu_item(__('Refresh'), () => {
            this.refresh();
        });
    }

    setup_layout() {
        this.container.empty().append(`
            <div class="valet-dashboard-wrapper p-3">
                <!-- Summary Metrics Cards -->
                <div class="row metric-cards-grid mb-4">
                    <div class="col-md-3 col-6 mb-3">
                        <div class="card metric-card border-warning text-center p-3 shadow-sm rounded-lg">
                            <div class="text-muted font-weight-bold text-uppercase small">${__('Awaiting Parking')}</div>
                            <div class="metric-value display-4 font-weight-bold text-warning" id="count-awaiting">0</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-3">
                        <div class="card metric-card border-primary text-center p-3 shadow-sm rounded-lg">
                            <div class="text-muted font-weight-bold text-uppercase small">${__('Parked Vehicles')}</div>
                            <div class="metric-value display-4 font-weight-bold text-primary" id="count-parked">0</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-3">
                        <div class="card metric-card border-danger text-center p-3 shadow-sm rounded-lg">
                            <div class="text-muted font-weight-bold text-uppercase small">${__('Retrieval Requests')}</div>
                            <div class="metric-value display-4 font-weight-bold text-danger" id="count-retrieval">0</div>
                        </div>
                    </div>
                    <div class="col-md-3 col-6 mb-3">
                        <div class="card metric-card border-info text-center p-3 shadow-sm rounded-lg">
                            <div class="text-muted font-weight-bold text-uppercase small">${__('On The Way')}</div>
                            <div class="metric-value display-4 font-weight-bold text-info" id="count-ontheway">0</div>
                        </div>
                    </div>
                </div>

                <!-- Search Filter & List Header -->
                <div class="card mb-4 shadow-sm rounded-lg">
                    <div class="card-body p-3">
                        <div class="row align-items-center">
                            <div class="col-md-6 mb-2 mb-md-0">
                                <h5 class="mb-0 font-weight-bold">${__('Active Parking Tickets')}</h5>
                            </div>
                            <div class="col-md-6">
                                <div class="input-group">
                                    <input type="text" id="valet-search-input" class="form-control" placeholder="${__('Search by Token or Vehicle Number...')}">
                                    <div class="input-group-append">
                                        <button class="btn btn-outline-secondary" type="button" id="btn-clear-search">Clear</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Active Tickets List -->
                <div id="tickets-container" class="tickets-container">
                    <div class="text-center p-5 text-muted">${__('Loading active tickets...')}</div>
                </div>
            </div>
        `);

        // Event listeners
        let timeout = null;
        this.container.find('#valet-search-input').on('input', (e) => {
            clearTimeout(timeout);
            this.search_query = $(e.target).val();
            timeout = setTimeout(() => {
                this.load_tickets();
            }, 300);
        });

        this.container.find('#btn-clear-search').on('click', () => {
            this.container.find('#valet-search-input').val('');
            this.search_query = "";
            this.load_tickets();
        });
    }

    refresh() {
        this.load_summary();
        this.load_tickets();
    }

    load_summary() {
        frappe.call({
            method: 'valet_parking.valet_parking.page.valet_dashboard.valet_dashboard.get_dashboard_summary',
            callback: (r) => {
                if (r.message) {
                    const s = r.message;
                    this.container.find('#count-awaiting').text(s['Awaiting Parking'] || 0);
                    this.container.find('#count-parked').text(s['Parked'] || 0);
                    this.container.find('#count-retrieval').text(s['Retrieval Requested'] || 0);
                    this.container.find('#count-ontheway').text(s['On The Way'] || 0);
                }
            }
        });
    }

    load_tickets() {
        frappe.call({
            method: 'valet_parking.valet_parking.page.valet_dashboard.valet_dashboard.get_active_tickets',
            args: { search_query: this.search_query },
            callback: (r) => {
                this.render_tickets(r.message || []);
            }
        });
    }

    render_tickets(tickets) {
        const $target = this.container.find('#tickets-container');
        $target.empty();

        if (!tickets || tickets.length === 0) {
            $target.append(`
                <div class="card p-5 text-center text-muted shadow-sm rounded-lg">
                    <h5>${__('No Active Parking Tickets Found')}</h5>
                    <p class="mb-0">${__('Click "+ New Ticket" to create a parking ticket.')}</p>
                </div>
            `);
            return;
        }

        const html = tickets.map(t => this.get_ticket_card_html(t)).join('');
        $target.append(html);

        // Bind quick action click handlers
        $target.find('.btn-status-action').on('click', (e) => {
            const btn = $(e.currentTarget);
            const token = btn.data('token');
            const nextStatus = btn.data('next-status');
            this.update_status(token, nextStatus, btn);
        });
    }

    get_ticket_card_html(t) {
        const statusBadges = {
            'Awaiting Parking': 'badge-warning',
            'Parked': 'badge-primary',
            'Retrieval Requested': 'badge-danger',
            'On The Way': 'badge-info',
            'Delivered': 'badge-success'
        };

        const currentBadge = statusBadges[t.status] || 'badge-secondary';

        let timeLabel = "Created";
        let timeVal = t.created_at || t.modified;
        if (t.status === "Parked" && t.parked_at) {
            timeLabel = "Parked";
            timeVal = t.parked_at;
        } else if (t.status === "Retrieval Requested" && t.retrieval_requested_at) {
            timeLabel = "Requested";
            timeVal = t.retrieval_requested_at;
        } else if (t.status === "On The Way" && t.on_the_way_at) {
            timeLabel = "On The Way";
            timeVal = t.on_the_way_at;
        } else if (t.status === "Delivered" && t.delivered_at) {
            timeLabel = "Delivered";
            timeVal = t.delivered_at;
        }

        let timeDisplay = timeVal;
        if (window.frappe && frappe.datetime && frappe.datetime.comment_when) {
            timeDisplay = frappe.datetime.comment_when(timeVal);
        }

        let actionBtn = "";
        if (t.status === "Awaiting Parking") {
            actionBtn = `<button class="btn btn-sm btn-primary btn-block font-weight-bold btn-status-action" data-token="${t.name}" data-next-status="Parked">
                            <i class="fa fa-car mr-1"></i> ${__('Mark as Parked')}
                         </button>`;
        } else if (t.status === "Parked") {
            actionBtn = `<button class="btn btn-sm btn-warning btn-block font-weight-bold btn-status-action" data-token="${t.name}" data-next-status="Retrieval Requested">
                            <i class="fa fa-bell mr-1"></i> ${__('Mark Retrieval Requested')}
                         </button>`;
        } else if (t.status === "Retrieval Requested") {
            actionBtn = `<button class="btn btn-sm btn-info btn-block font-weight-bold btn-status-action" data-token="${t.name}" data-next-status="On The Way">
                            <i class="fa fa-road mr-1"></i> ${__('Mark On The Way')}
                         </button>`;
        } else if (t.status === "On The Way") {
            actionBtn = `<button class="btn btn-sm btn-success btn-block font-weight-bold btn-status-action" data-token="${t.name}" data-next-status="Delivered">
                            <i class="fa fa-check-circle mr-1"></i> ${__('Mark Delivered')}
                         </button>`;
        } else {
            actionBtn = `<span class="text-muted small">${__('Completed')}</span>`;
        }

        return `
            <div class="card ticket-card mb-3 shadow-sm rounded-lg">
                <div class="card-body p-3">
                    <div class="row align-items-center">
                        <div class="col-md-3 col-12 mb-2 mb-md-0">
                            <div class="font-weight-bold text-dark h5 mb-0">
                                <a href="/app/parking-ticket/${t.name}" class="text-primary">${t.token_number || t.name}</a>
                            </div>
                            <span class="badge ${currentBadge} font-weight-normal mt-1">${t.status}</span>
                        </div>
                        <div class="col-md-3 col-6 mb-2 mb-md-0">
                            <div class="text-muted small">${__('Vehicle')}</div>
                            <div class="font-weight-bold text-uppercase">${t.vehicle_number} (${t.vehicle_type || 'Car'})</div>
                        </div>
                        <div class="col-md-3 col-6 mb-2 mb-md-0">
                            <div class="text-muted small">${__('WhatsApp Number')}</div>
                            <div class="font-weight-bold">${t.customer_whatsapp_number}</div>
                            <div class="text-muted small">${timeLabel}: ${timeDisplay}</div>
                        </div>
                        <div class="col-md-3 col-12 text-md-right mt-2 mt-md-0">
                            ${actionBtn}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    update_status(token, nextStatus, btn) {
        btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i> Updating...');

        frappe.call({
            method: 'valet_parking.valet_parking.page.valet_dashboard.valet_dashboard.update_ticket_status',
            args: {
                token_number: token,
                next_status: nextStatus
            },
            callback: (r) => {
                btn.prop('disabled', false);
                if (r.message && r.message.success) {
                    if (window.frappe && frappe.show_alert) {
                        frappe.show_alert({
                            message: r.message.message,
                            indicator: 'green'
                        }, 5);
                    }
                    this.refresh();
                } else {
                    if (window.frappe && frappe.msgprint) {
                        frappe.msgprint({
                            title: __('Update Failed'),
                            indicator: 'red',
                            message: (r.message && r.message.message) || __('Failed to update ticket status.')
                        });
                    }
                    this.refresh();
                }
            },
            error: (r) => {
                btn.prop('disabled', false);
                this.refresh();
            }
        });
    }
}
