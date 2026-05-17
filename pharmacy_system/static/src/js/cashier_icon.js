/** @odoo-module **/

// A robust helper to ensure the cashier register icon element is present in the target menu item
const injectCashierIcon = (element) => {
    // If this is the menu item element itself, make sure it has a .cashier-icon span
    let iconElement = element.classList.contains('cashier-icon') ? element : element.querySelector('.cashier-icon');

    if (!iconElement) {
        // Create the .cashier-icon element dynamically and prepend it into the menu link/anchor tag
        iconElement = document.createElement('span');
        iconElement.className = 'cashier-icon';

        const link = element.tagName === 'A' ? element : (element.querySelector('a') || element);
        link.prepend(iconElement);
    }
};

// Start a MutationObserver to handle dynamically loaded/rendered elements (e.g. Owl NavBar)
const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
        for (const node of mutation.addedNodes) {
            if (node.nodeType === Node.ELEMENT_NODE) {
                // 1. Check if the added node itself is the menu item or cashier icon
                if (node.getAttribute && node.getAttribute('data-menu-xmlid') === 'pharmacy_system.menu_pharmacy_medicine_pos') {
                    injectCashierIcon(node);
                } else if (node.classList && node.classList.contains('cashier-icon')) {
                    injectCashierIcon(node);
                }

                // 2. Find any nested menu items or cashier icons within the added node
                const targetMenuItems = node.querySelectorAll('[data-menu-xmlid="pharmacy_system.menu_pharmacy_medicine_pos"]');
                for (const menu of targetMenuItems) {
                    injectCashierIcon(menu);
                }

                const cashierIcons = node.querySelectorAll('.cashier-icon');
                for (const icon of cashierIcons) {
                    injectCashierIcon(icon);
                }
            }
        }
    }
});

// Run initially for any already existing elements in the DOM
const init = () => {
    const targetMenus = document.querySelectorAll('[data-menu-xmlid="pharmacy_system.menu_pharmacy_medicine_pos"]');
    for (const menu of targetMenus) {
        injectCashierIcon(menu);
    }

    const directIcons = document.querySelectorAll('.cashier-icon');
    for (const icon of directIcons) {
        injectCashierIcon(icon);
    }

    observer.observe(document.body, { childList: true, subtree: true });
};

if (document.body) {
    init();
} else {
    document.addEventListener('DOMContentLoaded', init);
}
