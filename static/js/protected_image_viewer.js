class ImageViewer {
  constructor() {
    this.images = [];
    this.currentIndex = 0;
    this.viewer = document.getElementById('image-viewer');
    this.img = document.getElementById('viewer-image');
    this.title = document.getElementById('viewer-title');
    
    if (!this.viewer || !this.img) return;
    
    this.state = {
      scale: 1,
      panning: false,
      pointX: 0,
      pointY: 0,
      startX: 0,
      startY: 0
    };

    this.init();
  }

  init() {
    document.addEventListener('click', (e) => {
      const trigger = e.target.closest('.image-preview-trigger');
      if (!trigger) return;
      
      const img = trigger.querySelector('img');
      if (!img) return;
      
      // Логика сбора списка картинок (как было раньше)
      const wrapper = trigger.closest('.email-attachments-wrapper');
      if (wrapper) {
        this.images = [...wrapper.querySelectorAll('.image-preview-trigger img')];
      } else {
        this.images = [...document.querySelectorAll('.image-preview-trigger img')];
      }
      
      this.currentIndex = this.images.indexOf(img);
      if (this.currentIndex === -1) this.currentIndex = 0;
      
      this.open(img);
    });
    
    this.setupControls();
  }

  setupControls() {
    // Закрытие
    document.querySelector('.viewer-close')?.addEventListener('click', () => this.close());
    document.querySelector('.image-viewer-backdrop')?.addEventListener('click', () => this.close());
    
    // Навигация
    document.querySelector('.viewer-prev')?.addEventListener('click', (e) => {
        e.stopPropagation(); 
        this.prev();
    });
    document.querySelector('.viewer-next')?.addEventListener('click', (e) => {
        e.stopPropagation(); 
        this.next();
    });
    
    // Клавиатура
    document.addEventListener('keydown', (e) => {
      if (this.viewer.classList.contains('hidden')) return;
      if (e.key === 'Escape') this.close();
      if (e.key === 'ArrowLeft') this.prev();
      if (e.key === 'ArrowRight') this.next();
    });
    
    // Зум колесиком
    this.img.addEventListener('wheel', (e) => {
        e.stopPropagation(); 
        e.preventDefault(); 
        this.zoom(e);
    }, { passive: false });
    
    // Перетаскивание (Mouse)
    this.img.addEventListener('mousedown', (e) => this.startPan(e));
    window.addEventListener('mousemove', (e) => this.doPan(e));
    window.addEventListener('mouseup', () => this.endPan());
    
    // Touch
    this.img.addEventListener('touchstart', (e) => {
        if(this.state.scale > 1) this.startPan(e.touches[0]);
    }, {passive: false});
    window.addEventListener('touchmove', (e) => {
         if(this.state.panning && this.state.scale > 1) {
             e.preventDefault();
             this.doPan(e.touches[0]);
         }
    }, {passive: false});
    window.addEventListener('touchend', () => this.endPan());
  }

  open(imgElement) {
    if (!imgElement) return;
    if (!this.images.length) return;
    
    const tempImg = new Image();
    tempImg.src = imgElement.src;
    
    tempImg.onload = () => {
        this.img.src = imgElement.src;
        this.title.textContent = imgElement.alt || imgElement.dataset.filename || '';
        
        this.viewer.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        
        this.resetTransform();
    };
  }

  resetTransform() {
      this.state.scale = 1;
      this.state.pointX = 0;
      this.state.pointY = 0;
      this.updateTransform();
  }

  zoom(e) {
    const delta = e.deltaY < 0 ? 0.1 : -0.1;
    const oldScale = this.state.scale;
    let newScale = oldScale + delta;
    newScale = Math.min(Math.max(newScale, 1), 5);
    
    if (newScale !== oldScale) {
        if (newScale <= 1) {
            this.state.scale = 1;
            this.state.pointX = 0;
            this.state.pointY = 0;
        } else {
            const rect = this.img.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const ratio = newScale / oldScale;
            this.state.pointX -= (mouseX * ratio - mouseX);
            this.state.pointY -= (mouseY * ratio - mouseY);
            this.state.scale = newScale;
        }
        this.updateTransform();
    }
  }

  updateTransform() {
    this.img.style.transform = `translate3d(${this.state.pointX}px, ${this.state.pointY}px, 0) scale(${this.state.scale})`;
    // Убираем анимацию во время драга для мгновенного отклика
    this.img.style.transition = this.state.panning ? 'none' : 'transform 0.2s cubic-bezier(0.25, 0.46, 0.45, 0.94)';
  }

  startPan(e) {
    if (this.state.scale <= 1) return;
    this.state.panning = true;
    this.state.startX = e.clientX - this.state.pointX;
    this.state.startY = e.clientY - this.state.pointY;
    this.img.style.cursor = 'grabbing';
    e.preventDefault(); // Важно для предотвращения выделения текста
  }

  doPan(e) {
    if (!this.state.panning) return;
    
    const clientX = e.clientX || e.pageX;
    const clientY = e.clientY || e.pageY;
    
    // Прямое обновление координат БЕЗ ограничений
    this.state.pointX = clientX - this.state.startX;
    this.state.pointY = clientY - this.state.startY;
    
    this.updateTransform();
  }

  endPan() {
    if (this.state.panning) {
        this.state.panning = false;
        this.img.style.cursor = 'grab';
    }
  }

  prev() {
    if (!this.images.length) return;
    this.currentIndex = (this.currentIndex - 1 + this.images.length) % this.images.length;
    this.update();
  }

  next() {
    if (!this.images.length) return;
    this.currentIndex = (this.currentIndex + 1) % this.images.length;
    this.update();
  }

  update() {
    if (!this.images.length) return;
    const img = this.images[this.currentIndex];
    if (!img) return;
    
    this.img.src = img.src;
    this.title.textContent = img.alt || '';
    this.resetTransform();
  }

  close() {
    this.viewer.classList.add('hidden');
    document.body.style.overflow = '';
  }
}

document.addEventListener('DOMContentLoaded', () => new ImageViewer());