const MEDIA_URL = window.mediaUrl || '/media/';

// Получаем сырые данные из Django (список строк)
const RAW_ICONS = window.defaultIcons || [];

export default {
    mediaUrl: MEDIA_URL,
    // Формируем путь к папке с иконками
    iconsPath: `/static/img/default_avatars/`,
    
    // rawData - это просто массив строк ['astronaut.png', ...], поэтому используем его напрямую
    availableIcons: Array.isArray(RAW_ICONS) ? RAW_ICONS : [], 
    
    maxFileSize: 5 * 1024 * 1024,
    allowedExtensions: ['jpg', 'jpeg', 'png'],

    hasUserPhoto: window.hasUserPhoto === true, 
    
    selectors: {
        container: '#avatarSelector',
        previewImg: '#avatarPreview',
        tabs: '.tab-btn',
        sections: '.avatar-section',
        photoSection: '#section-photo',
        iconSection: '#section-icons',
        dropZone: '#dropZone',
        fileInput: '#id_avatar',
        iconsGrid: '#iconsGrid',
        formDefaultAvatar: '#id_default_avatar',
        removePhotoBtn: '#removePhotoBtn',
        removeIconBtn: '#removeIconBtn',
        modeLabel: '#modeLabel',
        previewContainer: '#previewContainer'
    }
};