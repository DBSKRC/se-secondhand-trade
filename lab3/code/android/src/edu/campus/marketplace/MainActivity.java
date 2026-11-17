package edu.campus.marketplace;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.CookieManager;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

/** Displays the local campus marketplace and handles Android photo selection. */
public final class MainActivity extends Activity {
  private static final String MARKET_URL = "http://127.0.0.1:8871/";
  private static final int PICK_PHOTOS = 1;

  private WebView market;
  private LinearLayout errorView;
  private ValueCallback<Uri[]> pendingSelection;

  @Override
  public void onCreate(Bundle state) {
    super.onCreate(state);
    getWindow().setStatusBarColor(Color.rgb(245, 245, 245));
    getWindow().setNavigationBarColor(Color.rgb(245, 245, 245));
    getWindow().getDecorView().setSystemUiVisibility(
        View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR | View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);

    FrameLayout frame = new FrameLayout(this);
    market = new WebView(this);
    market.setBackgroundColor(Color.rgb(245, 245, 245));
    configureWebView();
    frame.addView(market, new FrameLayout.LayoutParams(-1, -1));
    errorView = makeErrorView();
    frame.addView(errorView, new FrameLayout.LayoutParams(-1, -1));
    setContentView(frame);
    connect();
  }

  private void configureWebView() {
    WebSettings settings = market.getSettings();
    settings.setJavaScriptEnabled(true);
    settings.setDomStorageEnabled(true);
    settings.setAllowFileAccess(false);
    settings.setAllowContentAccess(true);
    settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
    CookieManager.getInstance().setAcceptThirdPartyCookies(market, false);
    market.setWebViewClient(new WebViewClient() {
      @Override
      public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
        Uri uri = request.getUrl();
        return !("http".equals(uri.getScheme())
            && "127.0.0.1".equals(uri.getHost())
            && uri.getPort() == 8871);
      }

      @Override
      public void onReceivedError(
          WebView view, WebResourceRequest request, WebResourceError error) {
        if (request.isForMainFrame()) {
          market.setVisibility(View.GONE);
          errorView.setVisibility(View.VISIBLE);
        }
      }
    });
    market.setWebChromeClient(new WebChromeClient() {
      @Override
      public boolean onShowFileChooser(
          WebView view, ValueCallback<Uri[]> callback, FileChooserParams parameters) {
        return choosePhotos(callback);
      }
    });
  }

  private boolean choosePhotos(ValueCallback<Uri[]> callback) {
    if (pendingSelection != null) {
      pendingSelection.onReceiveValue(null);
    }
    pendingSelection = callback;
    Intent picker = new Intent(Intent.ACTION_GET_CONTENT);
    picker.setType("image/*");
    picker.addCategory(Intent.CATEGORY_OPENABLE);
    picker.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);
    try {
      startActivityForResult(picker, PICK_PHOTOS);
    } catch (ActivityNotFoundException failure) {
      finishPhotoSelection(null);
    }
    return true;
  }

  private void finishPhotoSelection(Uri[] result) {
    if (pendingSelection == null) {
      return;
    }
    ValueCallback<Uri[]> callback = pendingSelection;
    pendingSelection = null;
    callback.onReceiveValue(result);
  }

  @Override
  protected void onActivityResult(int request, int result, Intent data) {
    super.onActivityResult(request, result, data);
    if (request != PICK_PHOTOS) {
      return;
    }
    if (result == RESULT_OK && data != null && data.getClipData() != null) {
      int count = data.getClipData().getItemCount();
      Uri[] chosen = new Uri[count];
      for (int index = 0; index < count; index++) {
        chosen[index] = data.getClipData().getItemAt(index).getUri();
      }
      finishPhotoSelection(chosen);
    } else {
      finishPhotoSelection(WebChromeClient.FileChooserParams.parseResult(result, data));
    }
  }

  private LinearLayout makeErrorView() {
    LinearLayout panel = new LinearLayout(this);
    panel.setOrientation(LinearLayout.VERTICAL);
    panel.setGravity(Gravity.CENTER);
    int padding = (int) (32 * getResources().getDisplayMetrics().density);
    panel.setPadding(padding, padding, padding, padding);
    panel.setBackgroundColor(Color.rgb(245, 245, 245));

    TextView title = new TextView(this);
    title.setText("校园拾光");
    title.setTextColor(Color.rgb(24, 24, 24));
    title.setTextSize(31);
    panel.addView(title);

    TextView message = new TextView(this);
    message.setText("暂时无法连接电脑。启动校园拾光后端并连接安卓设备后重试。");
    message.setGravity(Gravity.CENTER);
    message.setPadding(0, padding / 2, 0, padding / 2);
    panel.addView(message);

    Button retry = new Button(this);
    retry.setText("重新连接");
    retry.setOnClickListener(view -> connect());
    panel.addView(retry);
    return panel;
  }

  private void connect() {
    errorView.setVisibility(View.GONE);
    market.setVisibility(View.VISIBLE);
    market.loadUrl(MARKET_URL);
  }

  @Override
  public void onBackPressed() {
    if (market.getVisibility() == View.VISIBLE && market.canGoBack()) {
      market.goBack();
    } else {
      super.onBackPressed();
    }
  }

  @Override
  protected void onDestroy() {
    finishPhotoSelection(null);
    if (market.getParent() instanceof FrameLayout) {
      ((FrameLayout) market.getParent()).removeView(market);
    }
    market.destroy();
    super.onDestroy();
  }
}
