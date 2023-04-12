/* NGLS - EXCLUSIVE */
// Original code: https://github.com/ovvn/dom-to-pdf
//
// Modifications:
// 1 ) dom-to-image-more: https://github.com/thislg/dom-to-pdf/commit/8d091d16999244aacacb9e2e9d0d8b0eb9eb4fed

const domToImage = require('dom-to-image-more');
const { jsPDF } = require('jspdf');

const cloneNode = (node, javascriptEnabled) => {
  let child;
  const clone =
    node.nodeType === 3
      ? document.createTextNode(node.nodeValue)
      : node.cloneNode(false);
  child = node.firstChild;
  while (child) {
    if (
      javascriptEnabled === true ||
      child.nodeType !== 1 ||
      child.nodeName !== 'SCRIPT'
    ) {
      clone.appendChild(cloneNode(child, javascriptEnabled));
    }
    child = child.nextSibling;
  }
  if (node.nodeType === 1) {
    if (node.nodeName === 'CANVAS') {
      clone.width = node.width;
      clone.height = node.height;
      clone.getContext('2d').drawImage(node, 0, 0);
    } else if (node.nodeName === 'TEXTAREA' || node.nodeName === 'SELECT') {
      clone.value = node.value;
    }
    clone.addEventListener(
      'load',
      () => {
        clone.scrollTop = node.scrollTop;
        clone.scrollLeft = node.scrollLeft;
      },
      true,
    );
  }
  return clone;
};

const createElement = (tagName, { className, innerHTML, style }) => {
  let i;
  let scripts;
  const el = document.createElement(tagName);
  if (className) {
    el.className = className;
  }
  if (innerHTML) {
    el.innerHTML = innerHTML;
    scripts = el.getElementsByTagName('script');
    i = scripts.length;
    // eslint-disable-next-line no-plusplus
    while (i-- > 0) {
      scripts[i].parentNode.removeChild(scripts[i]);
    }
  }
  Object.keys(style).forEach(key => {
    el.style[key] = style[key];
  });
  return el;
};

const isCanvasBlank = canvas => {
  const blank = document.createElement('canvas');
  blank.width = canvas.width;
  blank.height = canvas.height;
  const ctx = blank.getContext('2d');
  ctx.fillStyle = '#FFFFFF';
  ctx.fillRect(0, 0, blank.width, blank.height);
  return canvas.toDataURL() === blank.toDataURL();
};

export const downloadPdf = (dom, options, cb) => {
  const a4Height = 841.89;
  const a4Width = 595.28;
  let opts;
  let scaleObj;
  let style;
  const transformOrigin = 'top left';
  const pdfOptions = {
    orientation: 'p',
    unit: 'pt',
    format: 'a4',
    compress: true,
  };

  const {
    compression,
    excludeClassNames = [],
    excludeTagNames = ['button', 'input', 'select'],
    filename,
    overrideWidth,
    proxyUrl,
    scale,
  } = options;

  const overlayCSS = {
    position: 'fixed',
    zIndex: 1000,
    opacity: 0,
    left: 0,
    right: 0,
    bottom: 0,
    top: 0,
    // eslint-disable-next-line superset-theme-colors/no-literal-colors
    backgroundColor: 'rgba(0,0,0,0.8)',
  };
  if (overrideWidth) {
    overlayCSS.width = `${overrideWidth}px`;
  }

  const containerCSS = {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    height: 'auto',
    margin: 'auto',
    overflow: 'auto',
    // eslint-disable-next-line superset-theme-colors/no-literal-colors
    backgroundColor: 'white',
  };
  const overlay = createElement('div', {
    style: overlayCSS,
  });
  const container = createElement('div', {
    style: containerCSS,
  });
  container.appendChild(cloneNode(dom));
  overlay.appendChild(container);
  document.body.appendChild(overlay);

  const innerRatio = a4Height / a4Width;
  const containerWidth =
    overrideWidth || container.getBoundingClientRect().width;
  const pageHeightPx = Math.floor(containerWidth * innerRatio);
  const elements = container.querySelectorAll('*');

  // eslint-disable-next-line no-plusplus
  for (let i = 0, len = excludeClassNames.length; i < len; i++) {
    const clName = excludeClassNames[i];
    container.querySelectorAll(`.${clName}`).forEach(function (a) {
      return a.remove();
    });
  }

  // eslint-disable-next-line no-plusplus
  for (let j = 0, len1 = excludeTagNames.length; j < len1; j++) {
    const tName = excludeTagNames[j];
    const els = container.getElementsByTagName(tName);

    // eslint-disable-next-line no-plusplus
    for (let k = els.length - 1; k >= 0; k--) {
      if (!els[k]) {
        continue;
      }
      els[k].parentNode.removeChild(els[k]);
    }
  }

  Array.prototype.forEach.call(elements, el => {
    let endPage;
    let nPages;
    let pad;
    let startPage;

    const rules = {
      before: false,
      after: false,
      avoid: true,
    };
    const clientRect = el.getBoundingClientRect();

    if (rules.avoid && !rules.before) {
      startPage = Math.floor(clientRect.top / pageHeightPx);
      endPage = Math.floor(clientRect.bottom / pageHeightPx);
      nPages = Math.abs(clientRect.bottom - clientRect.top) / pageHeightPx;
      // Turn on rules.before if the el is broken and is at most one page long.
      if (endPage !== startPage && nPages <= 1) {
        rules.before = true;
      }
      // Before: Create a padding div to push the element to the next page.
      if (rules.before) {
        pad = createElement('div', {
          style: {
            display: 'block',
            height: `${pageHeightPx - (clientRect.top % pageHeightPx)}px`,
          },
        });
        el.parentNode.insertBefore(pad, el);
      }
    }
  });

  // Remove unnecessary elements from result pdf
  const filterFn = ({ classList, tagName }) => {
    let cName;
    let j;
    let len;
    if (classList) {
      // eslint-disable-next-line no-plusplus
      for (j = 0, len = excludeClassNames.length; j < len; j++) {
        cName = excludeClassNames[j];
        if (Array.prototype.indexOf.call(classList, cName) >= 0) {
          return false;
        }
      }
    }
    const ref = tagName != null ? tagName.toLowerCase() : undefined;
    return excludeTagNames.indexOf(ref) < 0;
  };

  opts = {
    filter: filterFn,
    proxy: proxyUrl,
  };

  if (scale) {
    const { offsetWidth, offsetHeight } = container;
    style = {
      transform: `scale(${scale})`,
      transformOrigin,
      width: `${offsetWidth}px`,
      height: `${offsetHeight}px`,
    };
    scaleObj = {
      width: offsetWidth * scale,
      height: offsetHeight * scale,
      quality: 1,
      style,
    };
    opts = Object.assign(opts, scaleObj);
  }

  return domToImage
    .toCanvas(container, opts)
    .then(canvas => {
      let h;
      let imgData;
      let page;
      let pageHeight;
      let w;
      // Remove overlay
      document.body.removeChild(overlay);
      // Initialize the PDF.
      const pdf = new jsPDF(pdfOptions);
      // Calculate the number of pages.
      const pxFullHeight = canvas.height;
      const nPages = Math.ceil(pxFullHeight / pageHeightPx);
      // Define pageHeight separately so it can be trimmed on the final page.
      pageHeight = a4Height;
      const pageCanvas = document.createElement('canvas');
      const pageCtx = pageCanvas.getContext('2d');
      pageCanvas.width = canvas.width;
      pageCanvas.height = pageHeightPx;
      page = 0;
      while (page < nPages) {
        if (page === nPages - 1 && pxFullHeight % pageHeightPx !== 0) {
          pageCanvas.height = pxFullHeight % pageHeightPx;
          pageHeight = (pageCanvas.height * a4Width) / pageCanvas.width;
        }
        w = pageCanvas.width;
        h = pageCanvas.height;
        pageCtx.fillStyle = 'white';
        pageCtx.fillRect(0, 0, w, h);
        pageCtx.drawImage(canvas, 0, page * pageHeightPx, w, h, 0, 0, w, h);
        // Don't create blank pages
        if (isCanvasBlank(pageCanvas)) {
          page += 1;
          continue;
        }
        // Add the page to the PDF.
        if (page) {
          pdf.addPage();
        }
        imgData = pageCanvas.toDataURL('image/PNG');
        pdf.addImage(
          imgData,
          'PNG',
          0,
          0,
          a4Width,
          pageHeight,
          undefined,
          compression,
        );
        page += 1;
      }
      if (typeof cb === 'function') {
        cb(pdf);
      }
      return pdf.save(filename);
    })
    .catch(error => {
      // Remove overlay
      document.body.removeChild(overlay);
      if (typeof cb === 'function') {
        cb(null);
      }
      // eslint-disable-next-line no-console
      console.error(error);
    });
};
