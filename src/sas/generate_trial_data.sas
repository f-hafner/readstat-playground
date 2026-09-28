/* ------------------------------------------------------------------ */
/* generate_trial_data.sas                                             */
/* To be run on SAS Viya                                               */
/*                                                                     */
/* Creates a sas7bdat file with 1,000,000 rows and 3 variables         */
/* mimicking a typical clinical-trial / statistical use case:          */
/*   subject_id : unique subject identifier                             */
/*   treatment  : treatment group (Control / Low dose / High dose)     */
/*   outcome    : continuous outcome measure (e.g. blood pressure)      */
/*                                                                     */
/* Output:     <outdir>/trial_data.sas7bdat                             */
/*                                                                     */
/* IMPORTANT (SAS Viya):                                               */
/*   The compute server cannot resolve *relative* paths in a          */
/*   LIBNAME statement, so SASROOT below must be the ABSOLUTE path     */
/*   to the folder that contains your "raw" directory, as seen by      */
/*   the compute server (not your browser/SAS Studio client).         */
/*   Adjust SASROOT to your environment, e.g.                          */
/*     /opt/sas/workspace                                               */
/*     /viyafiles/<your_user>                                           */
/*   Ask your admin, or find it with:                                   */
/*     %put %sysfunc(pathname(work));  <- shows the server-side WORK  */
/* ------------------------------------------------------------------ */

/* --- configuration: set this to the server-side absolute path ------- */
%let sasroot = /home/u64544907/sasuser.v94/; /* <-- ADJUST FOR YOUR SITE */
%let outdir  = &sasroot/raw;

/* --- verify the directory exists before trying to use it ----------- */
%let dir_ok = %sysfunc(fileexist(&outdir));
%if &dir_ok = 0 %then %do;
    %put ERROR: Directory &outdir does not exist on the compute server.;
    %put ERROR- Adjust the SASROOT macro at the top of this program.;
    %abort cancel;
%end;

%let n = 1000000;   /* number of subjects */

/* --- generate the data ---------------------------------------------- */
data work.trial_data;
    call streaminit(42);

    length subject_id 8
           treatment  $ 9;

    /* array of treatment labels for balanced randomisation */
    array trt[3] $9 _temporary_ ('Control', 'LowDose', 'HighDose');

    do i = 1 to &n;
        subject_id = i;

        /* balanced 1:1:1 randomisation */
        treatment = trt[rand('integer', 1, 3)];

        /* dose-dependent outcome: N(mu, 15) */
        if treatment = 'Control' then do;
            outcome = rand('normal', 120, 15);
        end;
        else if treatment = 'LowDose' then do;
            outcome = rand('normal', 115, 15);
        end;
        else do;
            outcome = rand('normal', 110, 15);
        end;

        keep subject_id treatment outcome;
        output;
    end;

    drop i;
run;

/* --- write permanent sas7bdat ---------------------------------------- */
libname out "&outdir";
data out.trial_data;
    set work.trial_data;
run;

/* --- quick sanity check ---------------------------------------------- */
proc contents data=out.trial_data;
run;

proc means data=out.trial_data n mean std min max;
    var outcome;
    class treatment;
run;

libname out clear;

