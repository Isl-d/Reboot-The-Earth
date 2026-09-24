// English and Arabic for the dashboard chrome. The decision text itself comes
// from the backend already written in both languages, so it is never translated
// here - that would risk changing a number.
export type Lang = 'en' | 'ar'

export type Verb = 'continue' | 'reroute' | 'sell' | 'donate' | 'hold'

/** Every label the dashboard chrome needs, in one shape per language. */
export interface Strings {
  title: string
  tagline: string
  fleet: string
  liveSensor: string
  demoClock: string
  mapClock: string
  monitored: string
  atRisk: string
  saved: string
  co2: string
  eventLog: string
  noEvents: string
  decision: string
  needsHuman: string
  recommended: string
  approve: string
  approved: string
  options: string
  option: string
  action: string
  arrival: string
  accepted: string
  rejected: string
  kgSaved: string
  extraKm: string
  value: string
  why: string
  comparison: string
  without: string
  with: string
  demoPanel: string
  door: string
  compressor: string
  sensor: string
  backupMode: string
  reset: string
  dispatch: string
  leaveAt: string
  insteadOf: string
  saves: string
  hours: string
  temperature: string
  air: string
  cargo: string
  limit: string
  freshness: string
  daysLeft: string
  onArrival: string
  storeNeeds: string
  ageing: string
  connected: string
  offline: string
  auditOk: string
  auditBroken: string
  scanBox: string
  sourceNote: string
  verbs: Record<Verb, string>
}

export const STRINGS: Record<Lang, Strings> = {
  en: {
    title: 'ColdGuard',
    tagline: 'live freshness for every pallet',
    fleet: 'Fleet',
    liveSensor: 'LIVE sensor',
    demoClock: 'Shelf-life clock',
    mapClock: 'Map',
    monitored: 'Monitored',
    atRisk: 'At risk',
    saved: 'Saved',
    co2: 'CO2e avoided',
    eventLog: 'Event log',
    noEvents: 'Nothing unusual yet.',
    decision: 'Decision needed',
    needsHuman: 'Needs a human decision',
    recommended: 'Recommended',
    approve: 'Approve',
    approved: 'Approved',
    options: 'Options',
    option: 'Option',
    action: 'Action',
    arrival: 'On arrival',
    accepted: 'Accepted',
    rejected: 'Rejected',
    kgSaved: 'kg saved',
    extraKm: 'Extra km',
    value: 'Value',
    why: 'Why',
    comparison: 'With and without ColdGuard',
    without: 'Without ColdGuard',
    with: 'With ColdGuard',
    demoPanel: 'Demo panel',
    door: 'Door',
    compressor: 'Cooling failure',
    sensor: 'Sensor fault',
    backupMode: 'Backup mode (simulate TRK-07)',
    reset: 'Reset demo',
    dispatch: 'Heat-aware dispatch',
    leaveAt: 'Leave at',
    insteadOf: 'instead of',
    saves: 'saves',
    hours: 'hours of freshness',
    temperature: 'Temperature',
    air: 'air sensor',
    cargo: 'cargo',
    limit: 'alert limit',
    freshness: 'Freshness',
    daysLeft: 'days of shelf life left',
    onArrival: 'days on arrival',
    storeNeeds: 'store needs',
    ageing: 'ageing',
    connected: 'live',
    offline: 'no data',
    auditOk: 'Audit chain verified',
    auditBroken: 'Audit chain broken',
    scanBox: 'Scan the box',
    sourceNote: 'Numbers computed on this laptop. The model only writes the words.',
    verbs: { continue: 'Continue', reroute: 'Reroute', sell: 'Sell', donate: 'Donate', hold: 'Hold' },
  },
  ar: {
    title: 'كولدغارد',
    tagline: 'نضارة حية لكل حمولة',
    fleet: 'الأسطول',
    liveSensor: 'حساس حي',
    demoClock: 'ساعة النضارة',
    mapClock: 'الخريطة',
    monitored: 'تحت المراقبة',
    atRisk: 'في خطر',
    saved: 'تم إنقاذه',
    co2: 'انبعاثات تم تفاديها',
    eventLog: 'سجل الأحداث',
    noEvents: 'لا شيء غير معتاد حتى الآن.',
    decision: 'قرار مطلوب',
    needsHuman: 'يحتاج قراراً بشرياً',
    recommended: 'الموصى به',
    approve: 'اعتماد',
    approved: 'تم الاعتماد',
    options: 'الخيارات',
    option: 'خيار',
    action: 'الإجراء',
    arrival: 'عند الوصول',
    accepted: 'مقبول',
    rejected: 'مرفوض',
    kgSaved: 'كجم تم إنقاذها',
    extraKm: 'كم إضافية',
    value: 'القيمة',
    why: 'السبب',
    comparison: 'مع كولدغارد وبدونه',
    without: 'بدون كولدغارد',
    with: 'مع كولدغارد',
    demoPanel: 'لوحة العرض',
    door: 'الباب',
    compressor: 'عطل التبريد',
    sensor: 'عطل الحساس',
    backupMode: 'الوضع الاحتياطي',
    reset: 'إعادة الضبط',
    dispatch: 'جدولة حسب الحرارة',
    leaveAt: 'الانطلاق في',
    insteadOf: 'بدلاً من',
    saves: 'يوفر',
    hours: 'ساعة من النضارة',
    temperature: 'الحرارة',
    air: 'حساس الهواء',
    cargo: 'الحمولة',
    limit: 'حد الإنذار',
    freshness: 'النضارة',
    daysLeft: 'يوم متبقٍ من العمر',
    onArrival: 'يوم عند الوصول',
    storeNeeds: 'يطلب المتجر',
    ageing: 'سرعة التقادم',
    connected: 'متصل',
    offline: 'لا توجد بيانات',
    auditOk: 'سلسلة التدقيق سليمة',
    auditBroken: 'سلسلة التدقيق مكسورة',
    scanBox: 'امسح الصندوق',
    sourceNote: 'كل الأرقام محسوبة على هذا الجهاز. النموذج يكتب النص فقط.',
    verbs: { continue: 'المتابعة', reroute: 'إعادة التوجيه', sell: 'البيع', donate: 'التبرع', hold: 'الاحتفاظ' },
  },
}
