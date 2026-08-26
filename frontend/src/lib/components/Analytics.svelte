<script lang="ts">
  import { PUBLIC_GA_MEASUREMENT_ID } from "$env/static/public";
  import { browser, dev } from "$app/environment";
  import { afterNavigate } from "$app/navigation";
  import { onMount } from "svelte";
  import { markAnalyticsReady } from "$lib/analytics";

  const enabled = browser && !dev && !!PUBLIC_GA_MEASUREMENT_ID;

  let ga4Loaded = $state(false);
  let initialPageViewSent = $state(false);

  if (enabled) {
    afterNavigate(() => {
      if (!ga4Loaded) return;
      if (initialPageViewSent) {
        initialPageViewSent = false;
        return;
      }
      if (window.location.pathname.startsWith("/admin")) return;
      sendPageView();
    });
  }

  onMount(() => {
    if (!enabled) return;

    let destroyed = false;

    (async () => {
      // 1. Initialize dataLayer + gtag shim
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () {
        window.dataLayer.push(arguments);
      };

      // 2. Set Consent Mode v2 defaults (Basic mode - no pings without consent)
      window.gtag("consent", "default", {
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        analytics_storage: "denied",
      });

      // 3. Dynamically import vanilla-cookieconsent (SSR-safe)
      const CookieConsent = await import("vanilla-cookieconsent");

      if (destroyed) return;

      // 4. Run consent banner
      CookieConsent.run({
        cookie: { sameSite: "Lax", secure: true },
        categories: {
          necessary: { enabled: true, readOnly: true },
          analytics: {},
        },
        onConsent: () => {
          if (CookieConsent.acceptedCategory("analytics")) {
            onAnalyticsAccepted();
          }
        },
        onChange: ({ changedCategories }) => {
          if (changedCategories.includes("analytics")) {
            if (CookieConsent.acceptedCategory("analytics")) {
              updateConsent(true);
              loadGA4();
            } else {
              updateConsent(false);
              deleteGACookies();
            }
          }
        },
        language: {
          default: "en",
          translations: {
            en: {
              consentModal: {
                title: "We use cookies",
                description:
                  'We use cookies to understand how visitors use our site. You can accept or decline analytics cookies. <a href="/privacy">Privacy Policy</a>',
                acceptAllBtn: "Accept all",
                acceptNecessaryBtn: "Only necessary",
                showPreferencesBtn: "Manage preferences",
              },
              preferencesModal: {
                title: "Cookie Preferences",
                acceptAllBtn: "Accept all",
                acceptNecessaryBtn: "Only necessary",
                savePreferencesBtn: "Save preferences",
                sections: [
                  {
                    title: "Essential Cookies",
                    description:
                      "Required for authentication and site functionality.",
                    linkedCategory: "necessary",
                  },
                  {
                    title: "Analytics Cookies",
                    description:
                      "Help us understand site usage via Google Analytics. No personal data is shared with advertisers.",
                    linkedCategory: "analytics",
                  },
                ],
              },
            },
          },
        },
      });
    })();

    // Cleanup for HMR
    return () => {
      destroyed = true;
      import("vanilla-cookieconsent").then((cc) => cc.reset());
    };
  });

  function onAnalyticsAccepted() {
    updateConsent(true);
    loadGA4();
  }

  function loadGA4() {
    if (ga4Loaded) return;
    const script = document.createElement("script");
    script.async = true;
    script.src = `https://www.googletagmanager.com/gtag/js?id=${PUBLIC_GA_MEASUREMENT_ID}`;
    script.onload = () => {
      ga4Loaded = true;
      window.gtag("js", new Date());
      window.gtag("config", PUBLIC_GA_MEASUREMENT_ID, {
        send_page_view: false,
      });
      // Release any conversion events queued before consent was granted.
      markAnalyticsReady();
      // Fire catch-up pageview for current page
      if (!window.location.pathname.startsWith("/admin")) {
        initialPageViewSent = true;
        sendPageView();
      }
    };
    document.head.appendChild(script);
  }

  function sendPageView() {
    const sanitizedPath = sanitizePath(window.location.pathname);
    window.gtag("event", "page_view", { page_path: sanitizedPath });
  }

  function sanitizePath(path: string): string {
    return path.replace(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi,
      "[id]",
    );
  }

  function updateConsent(granted: boolean) {
    window.gtag("consent", "update", {
      analytics_storage: granted ? "granted" : "denied",
    });
  }

  function deleteGACookies() {
    document.cookie.split(";").forEach((c) => {
      const name = c.trim().split("=")[0];
      if (name.startsWith("_ga")) {
        document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
      }
    });
  }
</script>
