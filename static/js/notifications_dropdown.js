(function ($) {
    $(function () {
        const $bell = $('#notificationBell');
        const $panel = $('#notificationPanel');
        const $list = $('#notificationList');
        const $badge = $('#notificationBadge');

        if (!$bell.length) {
            return;
        }

        const escapeHtml = (text) => {
            const div = document.createElement('div');
            div.textContent = text || '';
            return div.innerHTML;
        };

        const renderNotifications = (items) => {
            if (!items || !items.length) {
                $list.html(`
                    <div class="text-center py-4 text-muted">
                        <i class="fas fa-bell-slash fa-2x mb-2"></i>
                        <p class="mb-0">No notifications</p>
                    </div>
                `);
                return;
            }

            const html = items.map((n) => `
                <a class="notification-item text-decoration-none text-reset" href="${n.detail_url}">
                    <div class="notification-icon general"><i class="fas fa-bell"></i></div>
                    <div class="notification-content">
                        <div class="notification-title">${escapeHtml(n.title)}</div>
                        <div class="notification-message">${escapeHtml(n.message_preview)}</div>
                        <div class="notification-meta">
                            <span class="notification-time"><i class="far fa-clock"></i>${n.created_at}</span>
                        </div>
                    </div>
                </a>`).join('');
            $list.html(html);
        };

        const updateBadge = (count) => {
            if (count > 0) {
                $badge.text(count).show();
            } else {
                $badge.hide();
            }
        };

        const refreshNotifications = () => {
            $.getJSON('/notifications/api/summary')
                .done((data) => {
                    if (!data.success) return;
                    updateBadge(data.unread_count || 0);
                    renderNotifications(data.notifications || []);
                })
                .fail(() => {
                    $list.html('<div class="text-center py-3 text-danger">Failed to load notifications</div>');
                });
        };

        $bell.on('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            $panel.toggleClass('show');
            if ($panel.hasClass('show')) {
                refreshNotifications();
            }
        });

        $('#markAllReadBtn').on('click', () => {
            $.post('/notifications/api/read-all').always(() => {
                updateBadge(0);
                refreshNotifications();
            });
        });

        $(document).on('click', (e) => {
            if (!$(e.target).closest('#notificationWrapper').length) {
                $panel.removeClass('show');
            }
        });

        setInterval(refreshNotifications, 30000);
    });
})(jQuery);
