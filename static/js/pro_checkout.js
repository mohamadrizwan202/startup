"use strict";

document.addEventListener("DOMContentLoaded", async () => {
  const checkoutRoot = document.querySelector(".pro-checkout");
  const paymentError = document.getElementById("payment-error");
  const submitButton = document.querySelector(".pro-payment-submit");
  const todayAmount = document.querySelector(
    ".pro-payment-summary > div:first-child strong"
  );

  if (submitButton) {
    submitButton.disabled = true;
  }

  if (!checkoutRoot) {
    console.error("PureFyul checkout root not found.");
    return;
  }

  const publishableKey = checkoutRoot.dataset.stripePublishableKey;
  const sessionUrl = checkoutRoot.dataset.customSessionUrl;
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  const csrfToken = csrfMeta ? csrfMeta.getAttribute("content") : null;

  const showError = (message) => {
    if (paymentError) {
      paymentError.textContent = message;
    }
    console.error(message);
  };

  if (!publishableKey) {
    showError("Stripe publishable key is unavailable.");
    return;
  }

  if (!sessionUrl) {
    showError("Checkout session endpoint is unavailable.");
    return;
  }

  if (!csrfToken) {
    showError("Checkout security token is unavailable.");
    return;
  }

  if (typeof Stripe === "undefined") {
    showError("Stripe.js failed to load.");
    return;
  }

  try {
    const response = await fetch(sessionUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": csrfToken,
        "Accept": "application/json",
      },
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Unable to start checkout.");
    }

    if (!data.clientSecret) {
      throw new Error("Stripe Checkout Session did not return a client secret.");
    }

    const stripe = Stripe(publishableKey);

    const checkout = await stripe.initCheckoutElementsSdk({
      clientSecret: data.clientSecret,
    });

    const paymentElement = checkout.createPaymentElement();

    paymentElement.mount("#payment-element");

    const updateCheckoutState = (checkoutState) => {
      if (
        todayAmount &&
        checkoutState.total &&
        checkoutState.total.total &&
        checkoutState.total.total.amount
      ) {
        todayAmount.textContent = checkoutState.total.total.amount;
      }

      if (submitButton) {
        submitButton.disabled = !checkoutState.canConfirm;
      }
    };

    updateCheckoutState(checkout);
    checkout.on("change", updateCheckoutState);

    const loadActionsResult = await checkout.loadActions();

    if (loadActionsResult.type === "error") {
      throw new Error(loadActionsResult.error.message);
    }

    const actions = loadActionsResult.actions;

    if (!submitButton) {
      throw new Error("Checkout submit button is unavailable.");
    }

    submitButton.addEventListener("click", async () => {
      paymentError.textContent = "";
      submitButton.disabled = true;

      try {
        const confirmResult = await actions.confirm();

        // Successful confirmation normally redirects to return_url.
        // Reaching this branch usually means Stripe returned an immediate error.
        if (confirmResult.type === "error") {
          showError(confirmResult.error.message);
          submitButton.disabled = !checkout.canConfirm;
        }
      } catch (error) {
        showError(
          error instanceof Error
            ? error.message
            : "Unable to complete payment. Please try again."
        );
        submitButton.disabled = !checkout.canConfirm;
      }
    });

    console.log("PureFyul Stripe Payment Element mounted and checkout ready.");
  } catch (error) {
    showError(
      error instanceof Error
        ? error.message
        : "Unable to load the secure payment form."
    );
  }
});
