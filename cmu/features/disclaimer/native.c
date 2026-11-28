/* Independent Intro-only native feature. No OEM source bytes. */
typedef __UINT32_TYPE__ u32;
typedef __UINTPTR_TYPE__ word;
enum { COLUMNS = 24, ROWS = 166, CELLS = 249,
       INTRO_COLUMN = 10, INTRO_CONTEXT = 1023, SHOW_DISCLAIMER = 1491,
       DISCLAIMER_CELL = 88, CONTINUATION_CELL = 238, CONTINUATION_RULES = 13 };
typedef void (*Hook)(word);
typedef struct { word label; u32 count; void *rules; } Cell;
typedef struct {
    word label; u32 context; word f2, f3, f4, f5;
    Hook enter, exit; word f8;
} Column;
typedef struct {
    u32 columns_count, rows_count, cells_count;
    Column *columns; void *rows; Cell *cells; void *lookup;
} Machine;
typedef struct { u32 app, context, f2, bytes; void *data; } Context;
/* Ordinary callback builds outer words at sp+52; manager dereferences +12, then +4.
 * Actual libjciuiamgr instructions f56c/f730/f734, not a flattened event ID. */
typedef struct { u32 app, event; } EventData;
typedef struct { u32 handle, source, app; EventData *payload; u32 f4; } Event;
typedef struct {
    Machine *machine; Context *context; Cell *cells; Column *columns;
    void *disclaimer_rules, *continuation_rules, *rows, *lookup;
    volatile u32 *logo_state; Hook intro_exit;
    const char *quick_name;
} Binding;

#ifdef HOST_TEST
extern Binding cmu_binding(void);
#else
/* Hidden PC-relative symbol resolves to ELF VA0; its runtime address is load base. */
extern char cmu_image_base __attribute__((visibility("hidden")));
static Binding cmu_binding(void) {
    word base = (word)&cmu_image_base;
    Binding b;
    b.machine=(Machine *)(base+0x83dac); b.context=(Context *)(base+0x77d48);
    b.cells=(Cell *)(base+0x89b0c); b.columns=(Column *)(base+0x83dc8);
    b.disclaimer_rules=(void *)(base+0x8517c);
    b.continuation_rules=(void *)(base+0x88f5c);
    b.rows=(void *)(base+0x8387c); b.lookup=(void *)(base+0x77dbc);
    b.logo_state=(volatile u32 *)(base+0x8b2b0);
    b.intro_exit=(Hook)(base+0x1db88);
    b.quick_name=(const char *)(base+0x5cfe0);
    return b;
}
_Static_assert(sizeof(Machine)==28 && sizeof(Cell)==12 && sizeof(Column)==36, "ARM table ABI");
_Static_assert(sizeof(Context)==20 && sizeof(Event)==20, "ARM context/event ABI");
_Static_assert(__builtin_offsetof(Event,payload)==12 &&
               __builtin_offsetof(EventData,event)==4, "ARM nested event ABI");
#endif

extern word cmu_stock_process(word, Machine *, Event *, Context *, void *, void *);
extern void *cmu_copy(void *, const void *, word);
extern word cmu_uia_handle(void);
extern word cmu_focused_app(word);
extern int cmu_stop_service(const char *);
extern int cmu_log_allowed(int);
extern void cmu_log_write(int, u32, const char *, const char *, const char *,
                          u32, const char *, ...);

static void record(int level, const char *format, int result) {
    if (cmu_log_allowed(level))
        cmu_log_write(level,0xfff,"MMUI_SYSTEM","cmu_native_intro.c",
                      "cmu_intro_bypass",1,format,result);
}

/* Only installed in the cloned Intro header. Original warning hook stays once. */
static void cmu_intro_exit(word context) {
    Binding b=cmu_binding();
    int result;
    b.intro_exit(context);
    result=cmu_stop_service(b.quick_name);
    record(result==100 ? 5 : 2,"CMU_NATIVE_BYPASS quick rc=%d",result);
}

static int supported(Machine *m, Event *event, Context *current, Binding *b) {
    return m==b->machine && current==b->context && event &&
        current->context==INTRO_CONTEXT && event->payload &&
        event->payload->event==SHOW_DISCLAIMER &&
        m->columns_count==COLUMNS && m->rows_count==ROWS && m->cells_count==CELLS &&
        m->columns==b->columns && m->rows==b->rows &&
        m->cells==b->cells && m->lookup==b->lookup &&
        m->cells[DISCLAIMER_CELL].count==1 &&
        m->cells[DISCLAIMER_CELL].rules==b->disclaimer_rules &&
        m->cells[CONTINUATION_CELL].count==CONTINUATION_RULES &&
        m->cells[CONTINUATION_CELL].rules==b->continuation_rules &&
        m->columns[INTRO_COLUMN].context==INTRO_CONTEXT &&
        m->columns[INTRO_COLUMN].exit==b->intro_exit;
}

__attribute__((visibility("hidden")))
word cmu_native_process(word handle, Machine *machine, Event *event,
                        Context *current, void *a4, void *a5) {
    Binding b=cmu_binding();
    Machine local;
    Cell cells[CELLS];
    Column columns[COLUMNS];
    /* No waits, synthetic events, direct context assignment or table writes. */
    if (!supported(machine,event,current,&b) || *b.logo_state!=2 ||
        cmu_focused_app(cmu_uia_handle())!=1)
        return cmu_stock_process(handle,machine,event,current,a4,a5);
    /* The renderer disposes intro through stock DisposeIntroVideo only after
     * the incoming screen has completed its transition. Keep its native surface
     * alive here, including the denied-focus path. */
    record(5,"CMU_NATIVE_BYPASS deferred intro rc=%d",0);
    cmu_copy(&local,machine,sizeof local);
    cmu_copy(cells,machine->cells,sizeof cells);
    cmu_copy(columns,machine->columns,sizeof columns);
    cells[DISCLAIMER_CELL]=cells[CONTINUATION_CELL];
    columns[INTRO_COLUMN].exit=cmu_intro_exit;
    local.cells=cells;
    local.columns=columns;
    return cmu_stock_process(handle,&local,event,current,a4,a5);
}
