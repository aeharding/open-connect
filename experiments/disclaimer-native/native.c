/* Independent Intro-only native prototype. No OEM source bytes. */
typedef __UINT32_TYPE__ u32;
typedef __INT32_TYPE__ s32;
typedef __UINTPTR_TYPE__ word;
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
typedef struct { u32 source, app, event; void *payload; u32 f4; } Event;
typedef struct {
    Machine *machine; Context *context; Cell *cells; Column *columns;
    void *rules80, *rules194, *rows, *lookup;
    volatile u32 *logo_state; Hook intro_exit;
    const char *intro_command, *quick_name;
} Binding;

#ifdef HOST_TEST
extern Binding cmu_binding(void);
#else
/* Hidden PC-relative symbol resolves to ELF VA0; its runtime address is load base. */
extern char cmu_image_base __attribute__((visibility("hidden")));
static Binding cmu_binding(void) {
    word base = (word)&cmu_image_base;
    Binding b;
    b.machine=(Machine *)(base+0x59a9c); b.context=(Context *)(base+0x5145c);
    b.cells=(Cell *)(base+0x5daa8); b.columns=(Column *)(base+0x59ab8);
    b.rules80=(void *)(base+0x5abe8); b.rules194=(void *)(base+0x5d370);
    b.rows=(void *)(base+0x596ac); b.lookup=(void *)(base+0x514bc);
    b.logo_state=(volatile u32 *)(base+0x5ee48);
    b.intro_exit=(Hook)(base+0x13f6c);
    b.intro_command=(const char *)(base+0x4081c);
    b.quick_name=(const char *)(base+0x3d3ac);
    return b;
}
_Static_assert(sizeof(Machine)==28 && sizeof(Cell)==12 && sizeof(Column)==36, "ARM table ABI");
_Static_assert(sizeof(Context)==20 && sizeof(Event)==20, "ARM context/event ABI");
#endif

extern word cmu_stock_process(word, Machine *, Event *, Context *, void *, void *);
extern void *cmu_copy(void *, const void *, word);
extern int cmu_system(const char *);
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
        current->context==1021 && event->event==1470 &&
        m->columns_count==22 && m->rows_count==126 && m->cells_count==203 &&
        m->columns==b->columns && m->rows==b->rows &&
        m->cells==b->cells && m->lookup==b->lookup &&
        m->cells[79].count==1 && m->cells[79].rules==b->rules80 &&
        m->cells[193].count==9 && m->cells[193].rules==b->rules194 &&
        m->columns[9].context==1021 && m->columns[9].exit==b->intro_exit;
}

__attribute__((visibility("hidden")))
word cmu_native_process(word handle, Machine *machine, Event *event,
                        Context *current, void *a4, void *a5) {
    Binding b=cmu_binding();
    Machine local;
    Cell cells[203];
    Column columns[22];
    int result;
    /* No waits, synthetic events, direct context assignment or table writes. */
    if (!supported(machine,event,current,&b) || *b.logo_state!=2 ||
        cmu_focused_app(cmu_uia_handle())!=1)
        return cmu_stock_process(handle,machine,event,current,a4,a5);
    result=cmu_system(b.intro_command);
    record(result==0 ? 5 : 2,"CMU_NATIVE_BYPASS intro rc=%d",result);
    if (result!=0)
        return cmu_stock_process(handle,machine,event,current,a4,a5);
    *b.logo_state=0; /* Stock cleanup clears only on system() success. */
    cmu_copy(&local,machine,sizeof local);
    cmu_copy(cells,machine->cells,sizeof cells);
    cmu_copy(columns,machine->columns,sizeof columns);
    cells[79]=cells[193];
    columns[9].exit=cmu_intro_exit;
    local.cells=cells;
    local.columns=columns;
    return cmu_stock_process(handle,&local,event,current,a4,a5);
}
