#!/usr/bin/env python
import wpipe as wp
from astropy.io import fits
import time
import numpy as np
from deepCR import deepCR


def register(task):
    _temp = task.mask(source="*", name="start", value=task.name)
    _temp = task.mask(source="*", name="new_image", value="*")


"""
Original funtion docstring for tag_image.pl:

# This is a perl task that is part of the acs reduction pipeline.
# It's job is to review data that has been deposited into the target/proc   
# directory and tag each image with values from the header to make
# sorting of images simpler for later processing steps.
#
#
# This task is meant to be invoked in or on the proc subdirectory of a
# target.
# Configuration information is obtained from the target configuration
# utilites, which reference data stored in a configuration database.


"""


def tag_event_dataproduct(this_event):
    """
    Tags incoming dataproducts from fired event

    Parameters:
    -----------
    this_event : Event(OptOwner)
        a fired event of a WINGS pipeline.

    Returns:
    --------
    logprint the options for the current dataproduct in the log file.

    """

    # my_job.logprint(f"{this_event.options}")

    my_job = wp.Job()
    my_config = my_job.config
    this_dp_id = this_event.options["dp_id"]
    dp_fname_path = this_event.options["dp_fname_path"]
    this_target_id = this_event.options["target_id"]
    # config_id = this_event.options["config_id"]
    # filename = this_event.options["filename"]
    # my_job.logprint(f"{config_id} {this_dp_id} {this_target_id} {filename}")

    # Call dataproduct
    # this_dp = wp.DataProduct(this_dp_id, filename=filename, group="proc")
    my_rawdp = wp.DataProduct(int(this_dp_id), group="raw")
    target = wp.Target(this_target_id)
    proc_path = f"{target.datapath}/proc_default/"

    #! Make copy from raw directory to proc directory
    my_procdp = my_rawdp.make_copy(path=proc_path, group="proc")
    dp_fname = my_procdp.filename

    # ! CHANGE NAME OF PROC FILES
    hdu = fits.open(dp_fname_path)

    FILENAME = hdu[0].header["FILENAME"]
    TELESCOP = hdu[0].header["TELESCOP"]
    CAM = hdu[0].header["INSTRUME"]

    if ("JWST" not in TELESCOP):
        RA = hdu[0].header["RA_TARG"]
        DEC = hdu[0].header["DEC_TARG"]
        PA = hdu[0].header["PA_V3"]
        EXPTIME = hdu[0].header["EXPTIME"]
        EXPFLAG = hdu[0].header["EXPFLAG"]
        TARGNAME = hdu[0].header["TARGNAME"]
        PROPOSALID = hdu[0].header["PROPOSID"]
        DETECTOR = hdu[0].header["DETECTOR"]
        if ("WFC" in DETECTOR):
            FILTER1 = hdu[0].header["FILTER1"]
            FILTER2 = hdu[0].header["FILTER2"]
            if ("CLEAR" not in FILTER1):
                FILTER = FILTER1
            if ("CLEAR" not in FILTER2):
                FILTER = FILTER2
        else:
            FILTER = hdu[0].header["FILTER"]
    else:
        RA = hdu[0].header["TARG_DEC"]
        DEC = hdu[0].header["TARG_DEC"]
        PA = hdu[0].header["GS_V3_PA"]
        EXPTIME = hdu[0].header["EFFEXPTM"]
        EXPFLAG = "MANNORMAL"
        TARGNAME = hdu[0].header["TARGPROP"]
        PROPOSALID = hdu[0].header["PROGRAM"]
        DETECTOR = hdu[0].header["INSTRUME"]
        FILTER = hdu[0].header["FILTER"]


    hdu.close()
    dp_fname = dp_fname.rpartition("_")
    dp_fname = f"{dp_fname[0]}_{FILTER}_{dp_fname[2]}"
    my_job.logprint(f"{dp_fname}")
    # proc_dp_fname_path = proc_path + dp_fname  # * new dataproduct path

    # ! New dataproduct for proc directory files
    my_procdp.filename = dp_fname  # ! Changes filename
    FILENAME = dp_fname
    if ("_i2d" in FILENAME):
        TYPE = "DRIZZLED"
    if ("_drc" in FILENAME):
        TYPE = "DRIZZLED"
    if ("_flc" in FILENAME):
        TYPE = "SCIENCE"
    if ("_flt" in FILENAME):
        TYPE = "SCIENCE"
    if ("_crf" in FILENAME):
        TYPE = "SCIENCE"
    if ("_cal" in FILENAME):
        TYPE = "SCIENCE"
    my_procdp = wp.DataProduct(
        my_config,
        filename=dp_fname,
        group="proc",
        data_type="tagged",
        subtype=TYPE
    )
    # my_job.logprint(f"{my_procdp}, {tot_untagged_im}")
    my_job.logprint(f"{type(my_procdp.dp_id)}, {my_procdp.filename}")

    # my_job.logprint(f"{this_dp}")
    # my_job.logprint(f"{this_dp.target.datapath}")
    # * Dataproduct file pat

    # tag_event_dataproduct
    my_procdp_id = my_procdp.dp_id
    my_procdp = wp.DataProduct(
        int(my_procdp_id),
        options={
            "filename": FILENAME,
            "ra": RA,
            "dec": DEC,
            "telescope": TELESCOP,
            "detector": DETECTOR,
            "orientation": PA,
            "Exptime": EXPTIME,
            "Expflag": EXPFLAG,
            "cam": CAM,
            "filter": FILTER,
            "targname": TARGNAME,
            "proposalid": PROPOSALID,
            "type": TYPE,
            "dp_id": my_procdp_id,
            "target_id": this_target_id,
        },
    )
    my_job.logprint("Tagged Image Done")
    my_job.logprint(f"Subtype {my_procdp.subtype}")
    my_job.logprint(f"Tagged Image options{my_procdp.options}")
    return my_procdp


def imgclean(imgname, mdl, threshold, update=True):
    """
    imgname: input image name
    mdl: deepCR model
    threshold: threshold for deepCR
    update: update the original fits file or not
    Three options for CR identification in the pipeline running:

    1. regular default pipeline (same as old pipeline):  
    - Overwrite all original DQ cr flag (to zero) for raw flc.fits data from MAST, and then perform astrodrizzle to identify DQ flag for cr
    - NOT need to specify the parameter "resetbits" in drizzlepac.astrodrizzle.AstroDrizzle, using default = 4096
    - "resetbits" allow to specify which DQ bits should be reset to a value of 0; prior to starting any of AstroDrizzle process steps

    2. NOT run deepCR within the pipeline, BUT use deepCR-processed images
    - The raw flc.fits images haven been processed using deepCR beforehand. The original DQ flag cr from MAST raw data has been removed, and updated to the DQ cr flags using deepCR
    - In the pipeline, NEED to specify the parameter "resetbits = 0" in drizzlepac.astrodrizzle.AstroDrizzle, to KEEP all deepCR-identified DQ bits, and then perform astrodrizzle TOO
    - The cr identified in both steps would be combined together to the final DQ flag

    3. RUN deepCR within the pipeline, go through deepCR task
    - Input need: trained model; self-defined threshold; update= True
    - And see option 2., also NEED to specify the parameter "resetbits = 0" to keep all deepCR-identified DQ bits, and then perform astrodrizzle TOO
    Below is the python function to perform deepCR on each image, and update the DQ cr flag:

    """
    # my_job.logprint("\nRunning DeepCR imgclean function")
    my_job.logprint(
        f"\n image_name: {imgname}, \nthreshold: {threshold}, \nupdate is: {update}")
    # print('image_name:', imgname)
    # print('threshold:', threshold)
    # print('update is', update)
    # open the image with all extensions
    if update:
        imgall = fits.open(imgname, mode='update')
    else:
        imgall = fits.open(imgname)

    # process each chip/extension of the image, manually normalize the input
    imgorichip1 = imgall[1].data
    imgorichip1mean = imgorichip1.mean()
    imgorichip1std = imgorichip1.std()
    imgnormchip1 = (imgorichip1 - imgorichip1mean) / imgorichip1std
    my_job.logprint(f"imgnormchip1: {imgnormchip1.shape}")
    imgorichip2 = imgall[4].data
    imgorichip2mean = imgorichip2.mean()
    imgorichip2std = imgorichip2.std()
    imgnormchip2 = (imgorichip2 - imgorichip2mean) / imgorichip2std
    my_job.logprint(f"imgnormchip2: {imgnormchip2.shape}")

    my_job.logprint('----chip1----')
    my_job.logprint('mdl cleaning')
    maskimgchip1, cleaned_imgchip1 = mdl.clean(
        imgnormchip1, threshold=threshold, inpaint='medmask')  # ! crashes computer
    my_job.logprint('mdl DONE cleaning')
    maskimgchip1 = np.float32(maskimgchip1)
    dqchip1 = imgall[3].data
    my_job.logprint(
        f"original MAST DQ: {len(np.where((dqchip1&4096) == 4096)[0])}")
    # print('original MAST DQ:', len(np.where((dqchip1&4096) == 4096)[0]))
    dqchip1[dqchip1 & 4096 == 4096] ^= 4096
    my_job.logprint(
        f"remove original check: {len(np.where((dqchip1&4096) == 4096)[0])}")
    # print('remove original check:', len(np.where((dqchip1&4096) == 4096)[0]))
    dqchip1[maskimgchip1 == 1] |= 4096
    my_job.logprint(
        f"after deepCR DQ: {len(np.where((dqchip1&4096) == 4096)[0])}")
    # print('after deepCR DQ:', len(np.where((dqchip1&4096) == 4096)[0]))
    imgall[3].data = dqchip1
    my_job.logprint('CR DQ update done')

    my_job.logprint('\n----chip2----')
    my_job.logprint('mdl cleaning')
    maskimgchip2, cleaned_imgchip2 = mdl.clean(
        imgnormchip2, threshold=threshold, inpaint='medmask')
    my_job.logprint('mdl DONE cleaning')
    maskimgchip2 = np.float32(maskimgchip2)
    dqchip2 = imgall[6].data
    # # print('original MAST DQ:', len(np.where((dqchip2&4096) == 4096)[0]))
    my_job.logprint(
        f'original MAST DQ: {len(np.where((dqchip2&4096) == 4096)[0])}')
    dqchip2[dqchip2 & 4096 == 4096] ^= 4096
    # # print('remove original check:', len(np.where((dqchip2&4096) == 4096)[0]))
    my_job.logprint(
        f'remove original check: {len(np.where((dqchip2&4096) == 4096)[0])}')
    dqchip2[maskimgchip2 == 1] |= 4096
    # # print('after deepCR DQ:', len(np.where((dqchip2&4096) == 4096)[0]))
    my_job.logprint(
        f'after deepCR DQ:: {len(np.where((dqchip2&4096) == 4096)[0])}')
    imgall[6].data = dqchip2
    my_job.logprint('CR DQ update done')

    if update:
        imgall.flush()
        my_job.logprint('update original fits file done')
    else:
        my_job.logprint('original fits file not updated!')
    return


if __name__ == "__main__":
    my_pipe = wp.Pipeline()
    my_job = wp.Job()

    # ! Get the firing event obj
    # * Selecting parent event object
    this_event = my_job.firing_event
    config_id = this_event.options["config_id"]
    my_job.logprint(f"This Event: {this_event}")

    #! Write parent job event option parameters
    compname = this_event.options["comp_name"]
    parent_job = this_event.parent_job

    # ! Start tag_event_dataproduct function
    my_dp = tag_event_dataproduct(this_event)

    #! Fire DeepCR event after tagging
    my_config_param = my_job.config.parameters
    my_job.logprint(
        f"MY CONFIG PARM: {my_config_param}, {type(my_config_param)}")
    my_job.logprint(
        f"\n parameter atrributs: {dir(my_job.config.parameters)}")
    my_job.logprint(
        f"\nRUN_DEEPCR setting: {my_job.config.parameters['RUN_DEEPCR']}, {type(my_job.config.parameters['RUN_DEEPCR'])}")
    if "UVIS" in my_dp.options["detector"]:
        if my_config_param['RUN_DEEPCR'] == 'T' and my_config_param['machine'] == 'remote':
            my_job.logprint("Running DeepCR REMOTELY)")
            #! #########################################
            #! DeepCR parameters from config file
            deepcr_pth_mask = my_config_param["deepcr_pth"]
            threshold = my_config_param["deepcr_threshold"]
            mdl = deepCR(mask=deepcr_pth_mask, hidden=32)
            # file path to image being tagged currently
            procdp_path = my_dp.target.datapath + "/proc_default/"
            my_job.logprint(f"\n {my_dp}, {type(my_dp)}, {procdp_path}")

            dp_filepath = procdp_path + "/" + my_dp.filename
            my_job.logprint(f"{dp_filepath}")

            # * imgclean function
            # Run DeepCR on each image
            imgclean(dp_filepath, mdl, threshold, update=True)

    elif my_config_param['RUN_DEEPCR'] == 'F':
        my_job.logprint(f"Not running DeepCR")
        # tag = str(update_option),

    elif my_config_param['RUN_DEEPCR'] == 'Keep':
        my_job.logprint(f"Keeping DQ as RUN_DEEPCR is set to Keep.")
        # tag = str(update_option),

    else:
        my_job.logprint(
            f"RUN_DEEPCR parameter not set... Not running DeepCR.")
        # tag = str(update_option),

    # ! Check of all images have been tagged
    update_option = parent_job.options[compname]
    update_option += 1
    to_run = this_event.options["to_run"]
    my_job.logprint(f"parent_job options: {parent_job.options}")
    my_job.logprint(f"{update_option}/{to_run} TAGGED")
    if this_event.options["to_run"] == update_option:
        my_job.logprint(f"This Job Options: {my_job.options}")
        compname = "completed_" + this_event.options["target_name"]
        new_option = {compname: 0}
        my_job.options = new_option
        my_job.logprint(f"Updated Job Options: {my_job.options}")

        # List of all filters in target
        my_config = my_job.config  # Get configuration for the job
        my_dp = wp.DataProduct.select(
            dpowner_id=my_config.config_id, data_type="tagged"
        )  # Get dataproducts associated with configuration (ie. dps for my_target)

        filters = []  # Making list of filters for target
        jwfilters = []
        adrizfilters = []
        my_job.logprint(
            "All Dataproducts that are done being tagged and ready for DeepCR task!")
        for dp in my_dp:
            my_job.logprint(f"\n{dp.filename}, {dp.options['filter']}")
            filters.append(dp.options["filter"])
            if dp.options["telescope"] == "JWST":
                jwfilters.append(dp.options["filter"])
            else:
                adrizfilters.append(dp.options["filter"])
                if my_config_param['RUN_DEEPCR'] == 'T' and my_config_param['machine'] == 'local':
                    my_job.logprint("Running DeepCR LOCALLY")
                    #! #########################################
                    #! DeepCR parameters from config file
                    deepcr_pth_mask = my_config_param["deepcr_pth"]
                    threshold = my_config_param["deepcr_threshold"]
                    mdl = deepCR(mask=deepcr_pth_mask, hidden=32)

                    #! Run DeepCR on each dataproducts
                    procdp_path = dp.target.datapath + "/proc_default/"  # file path to image
                    # my_job.logprint(f"\n {dp}, {type(dp)}, {procdp_path}")

                    if dp.filename.split("_")[-1] == "flc.fits":
                        ext_flc = dp.filename.split("_")[-1]
                        # my_job.logprint(ext_flc)

                        dp_filepath = procdp_path + "/" + dp.filename
                        my_job.logprint(
                            f"Running imgclean on {dp.filename}...")
                        imgclean(dp_filepath, mdl, threshold, update=True)

                elif my_config_param['RUN_DEEPCR'] == 'F':
                    my_job.logprint(f"Not running DeepCR")
                    # tag = str(update_option),

                elif my_config_param['RUN_DEEPCR'] == 'Keep':
                    my_job.logprint(
                        f"Keeping DQ as RUN_DEEPCR is set to Keep.")
                    # tag = str(update_option),

                else:
                    my_job.logprint(
                        f"RUN_DEEPCR parameter not set... Not running DeepCR.")
                    # tag = str(update_option),

        all_filters = set(
            filters
        )  # Remove duplicates to get array of different filters for target
        adriz_filters = set(
            adrizfilters
        )  # Remove duplicates to get array of different filters for target

        my_config.parameters["filters"] = ",".join(
            all_filters
        )  # add list of filters to configuration
        my_config.parameters["adrizfilters"] = ",".join(
            adriz_filters
        )  # add list of filters to configuration
        # ? my_config.save()  # save configuration to database
        my_job.logprint(f"MY CONFIG PARM: {my_config.parameters}")

        num_all_filters = len(all_filters)
        num_adriz_filters = len(adriz_filters)
        my_job.logprint(
            f"{num_all_filters} filters found for target {this_event.options['target_name']}")

        #! Fire next task astrodrizzle
        my_job.logprint("FIRING NEXT ASTRODRIZZLE TASK")
        if len(adriz_filters) > 0:
            for i in adriz_filters:
                my_job.logprint(f"{i},{type(str(i))}")
                my_event = my_job.child_event(
                    name="astrodrizzle",
                    options={
                        "target_name": this_event.options["target_name"],
                        "target_id": this_event.options["target_id"],
                        "config_id": this_event.options["config_id"],
                        "to_run": len(adriz_filters),  # num of filter to run
                        "filter": str(i),
                        "comp_name": compname
                    },
                    tag=str(
                        i
                    ),  # ! need to set a tag for each event if firering multiple events with the same name
                )
                my_event.fire()
        else:
            my_job.logprint(
                f"AstroDrizzle step complete for {this_event.options['target_name']}, firing find reference task.")
            next_event = my_job.child_event(
                name="find_ref",
                options={"target_id": this_event.options["target_id"]}
            )  # next event
            next_event.fire()

        time.sleep(150)

        # my_job.logprint(f"Firing Event Options: {my_event.options}")

    else:
        pass


########################################
# Code originally from astrodrizzle that can be used here instead

# my_config = my_job.config  # Get configuration for the job

# my_dp = wp.DataProduct.select(dpowner_id=my_config.config_id, data_type="image", subtype="tagged") # Get dataproducts associated with configuration (ie. dps for my_target)

# filters = []  # Making array of filters for target
# for dp in my_dp:
# filters.append(dp.options["filter"])
# all_filters = set(filters) # Remove duplicates to get array of different filters for target

# my_config.parameters['filters']= ','.join(all_filters) #add list of filters to configuration

# num_all_filters = len(all_filters)
# my_job.logprint(f"{num_all_filters} filters found for target {my_target.name}")
