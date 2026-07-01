/** 工具箱侧边栏：标签切换与 iframe 懒加载 */
const UIUtils = {
  resolveToolPath(rel) {
    let path = location.pathname;
    if (!path.endsWith('/')) {
      path = path.endsWith('.html')
        ? path.slice(0, path.lastIndexOf('/') + 1)
        : path + '/';
    }
    return new URL(rel, location.origin + path).href;
  },

  initTabs() {
    const navLinks = document.querySelectorAll('.nav-link');

    const clearTabMotionStyle = (el) => {
      el.style.opacity = '';
      el.style.transform = '';
    };

    const loadTabIframe = (panel) => {
      const iframe = panel.querySelector('iframe');
      if (iframe && iframe.hasAttribute('data-src')) {
        iframe.src = UIUtils.resolveToolPath(iframe.getAttribute('data-src'));
        iframe.removeAttribute('data-src');
      }
    };

    const activateContent = (tabId, { animateEnter = false } = {}) => {
      const newContent = document.getElementById(tabId);
      if (!newContent) return;

      if (animateEnter) {
        newContent.classList.add('active');
        newContent.style.opacity = '0';
        newContent.style.transform = 'translateY(20px)';
        loadTabIframe(newContent);

        requestAnimationFrame(() => {
          requestAnimationFrame(() => {
            newContent.style.opacity = '1';
            newContent.style.transform = 'translateY(0)';
          });
        });

        const onEntered = (e) => {
          if (e.target !== newContent || e.propertyName !== 'transform') return;
          newContent.removeEventListener('transitionend', onEntered);
          clearTabMotionStyle(newContent);
        };
        newContent.addEventListener('transitionend', onEntered);
      } else {
        newContent.classList.add('active');
        newContent.style.opacity = '1';
        newContent.style.transform = 'translateY(0)';
        loadTabIframe(newContent);
      }

      if (tabId && history.replaceState) {
        history.replaceState(null, '', '#' + tabId);
      }
    };

    navLinks.forEach(link => {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        const tabId = this.getAttribute('data-tab');
        if (this.classList.contains('active')) {
          activateContent(tabId);
          return;
        }

        navLinks.forEach(l => l.classList.remove('active'));
        this.classList.add('active');

        const switchContent = () => {
          const activeContent = document.querySelector('.tab-content.active');
          if (activeContent && activeContent.id !== tabId) {
            activeContent.style.opacity = '0';
            activeContent.style.transform = 'translateY(20px)';

            setTimeout(() => {
              activeContent.classList.remove('active');
              clearTabMotionStyle(activeContent);
              activateContent(tabId, { animateEnter: true });
            }, 100);
          } else {
            activateContent(tabId, { animateEnter: true });
          }
        };

        requestAnimationFrame(switchContent);
      });
    });

    const hash = window.location.hash.replace(/^#/, '');
    if (hash) {
      const tab = Array.from(navLinks).find(link => link.getAttribute('data-tab') === hash);
      if (tab) {
        setTimeout(() => {
          if (!tab.classList.contains('active')) tab.click();
          else activateContent(hash);
        }, 50);
      }
    }
  }
};
