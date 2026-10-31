export const projects = [
 {id:'solar',name:'Solar panel mapping',subtitle:'Find the energy hiding in plain sight.',task:'Segmentation',dataset:'PV4GER-Seg',score:'84.2',metric:'Mean IoU',experiments:6,status:'Completed',color:'solar'},
 {id:'land',name:'Land cover classification',subtitle:'A clearer picture of the world below.',task:'Classification',dataset:'EuroSAT',score:'93.6',metric:'Accuracy',experiments:4,status:'Completed',color:'land'},
 {id:'kiln',name:'Brick kiln detection',subtitle:'Turn satellite imagery into useful signals.',task:'Classification',dataset:'Brick-Kiln',score:'89.1',metric:'Accuracy',experiments:3,status:'Completed',color:'kiln'}
];
export const experiments = [
 {id:'06',name:'Foreground-aware loss',change:'Give smaller solar panels a stronger signal',score:84.2,delta:'+2.4',time:'12m 08s',state:'Best model'},
 {id:'05',name:'Stronger augmentation',change:'Random rotation and color variation',score:81.8,delta:'+1.1',time:'10m 42s',state:'Retained'},
 {id:'04',name:'Higher learning rate',change:'Increase learning rate to 0.003',score:79.6,delta:'−1.1',time:'8m 16s',state:'Reverted'},
 {id:'03',name:'Cosine learning schedule',change:'Decay learning rate over the run',score:80.7,delta:'+2.3',time:'11m 21s',state:'Retained'},
 {id:'02',name:'Pretrained encoder',change:'Start from pretrained visual features',score:78.4,delta:'+4.8',time:'9m 53s',state:'Retained'},
 {id:'01',name:'Starting recipe',change:'Establish a fixed reference',score:73.6,delta:'—',time:'7m 04s',state:'Reference'}
];
